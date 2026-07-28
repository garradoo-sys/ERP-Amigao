import csv
import io
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, ConfigDict
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./amigao.db")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret")
ALGORITHM = "HS256"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120), default="Administrador")
    role: Mapped[str] = mapped_column(String(50), default="admin")
    active: Mapped[int] = mapped_column(Integer, default=1)

class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    document: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="customer")

class Vehicle(Base):
    __tablename__ = "vehicles"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    plate: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    brand: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    year: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    mileage: Mapped[int] = mapped_column(Integer, default=0)
    customer: Mapped[Customer] = relationship(back_populates="vehicles")

class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    stock: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    minimum_stock: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    brand: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class WorkOrder(Base):
    __tablename__ = "work_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"))
    status: Mapped[str] = mapped_column(String(40), default="Aberta")
    complaint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    diagnosis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(engine)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
app = FastAPI(title="Amigão ERP API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
def seed_admin():
    with SessionLocal() as db:
        username = os.getenv("ADMIN_USER", "admin")
        if not db.scalar(select(User).where(User.username == username)):
            db.add(User(username=username, password_hash=pwd_context.hash(os.getenv("ADMIN_PASSWORD", "admin123")), full_name="Administrador Amigão", role="admin"))
            db.commit()

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

class CustomerIn(BaseModel):
    name: str
    document: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None

class VehicleIn(BaseModel):
    customer_id: int
    plate: str
    brand: Optional[str] = None
    model: Optional[str] = None
    year: Optional[str] = None
    mileage: int = 0

class ProductIn(BaseModel):
    code: str
    name: str
    stock: Decimal = Decimal("0")
    minimum_stock: Decimal = Decimal("0")
    cost: Decimal = Decimal("0")
    price: Decimal = Decimal("0")
    category: Optional[str] = None
    brand: Optional[str] = None

class WorkOrderIn(BaseModel):
    customer_id: int
    vehicle_id: int
    status: str = "Aberta"
    complaint: Optional[str] = None
    diagnosis: Optional[str] = None
    total: Decimal = Decimal("0")

def create_token(user: User):
    payload = {"sub": str(user.id), "username": user.username, "role": user.role, "exp": datetime.now(timezone.utc) + timedelta(hours=10)}
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)

def current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(db_session)):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        user = db.get(User, int(payload["sub"]))
    except (JWTError, KeyError, ValueError):
        raise HTTPException(401, "Sessão inválida")
    if not user or not user.active:
        raise HTTPException(401, "Usuário inativo")
    return user

@app.post("/auth/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(db_session)):
    user = db.scalar(select(User).where(User.username == form.username))
    if not user or not pwd_context.verify(form.password, user.password_hash):
        raise HTTPException(401, "Usuário ou senha incorretos")
    return Token(access_token=create_token(user), user={"name": user.full_name, "role": user.role, "username": user.username})

@app.get("/health")
def health():
    return {"status": "ok", "system": "Amigão ERP"}

@app.get("/dashboard")
def dashboard(_: User = Depends(current_user), db: Session = Depends(db_session)):
    return {
        "customers": db.scalar(select(func.count(Customer.id))) or 0,
        "vehicles": db.scalar(select(func.count(Vehicle.id))) or 0,
        "products": db.scalar(select(func.count(Product.id))) or 0,
        "open_orders": db.scalar(select(func.count(WorkOrder.id)).where(WorkOrder.status != "Finalizada")) or 0,
        "low_stock": db.scalar(select(func.count(Product.id)).where(Product.stock <= Product.minimum_stock)) or 0,
        "inventory_value": float(db.scalar(select(func.coalesce(func.sum(Product.stock * Product.cost), 0))) or 0),
    }

@app.get("/customers")
def list_customers(_: User = Depends(current_user), db: Session = Depends(db_session)):
    return db.scalars(select(Customer).order_by(Customer.name)).all()

@app.post("/customers")
def create_customer(data: CustomerIn, _: User = Depends(current_user), db: Session = Depends(db_session)):
    obj = Customer(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@app.get("/vehicles")
def list_vehicles(_: User = Depends(current_user), db: Session = Depends(db_session)):
    rows = db.scalars(select(Vehicle).order_by(Vehicle.plate)).all()
    return [{"id": v.id, "customer_id": v.customer_id, "plate": v.plate, "brand": v.brand, "model": v.model, "year": v.year, "mileage": v.mileage} for v in rows]

@app.post("/vehicles")
def create_vehicle(data: VehicleIn, _: User = Depends(current_user), db: Session = Depends(db_session)):
    obj = Vehicle(**data.model_dump(), plate=data.plate.upper())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@app.get("/products")
def list_products(_: User = Depends(current_user), db: Session = Depends(db_session)):
    rows = db.scalars(select(Product).order_by(Product.name).limit(5000)).all()
    return [{"id": p.id, "code": p.code, "name": p.name, "stock": float(p.stock), "minimum_stock": float(p.minimum_stock), "cost": float(p.cost), "price": float(p.price), "category": p.category, "brand": p.brand} for p in rows]

@app.post("/products")
def create_product(data: ProductIn, _: User = Depends(current_user), db: Session = Depends(db_session)):
    if db.scalar(select(Product).where(Product.code == data.code)):
        raise HTTPException(409, "Código já cadastrado")
    obj = Product(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


def br_decimal(value):
    if value is None or str(value).strip() == "": return Decimal("0")
    text = str(value).strip().replace("R$", "").replace(" ", "")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try: return Decimal(text)
    except InvalidOperation: return Decimal("0")

@app.post("/products/import")
async def import_products(file: UploadFile = File(...), _: User = Depends(current_user), db: Session = Depends(db_session)):
    raw = await file.read()
    text = None
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc); break
        except UnicodeDecodeError:
            continue
    if text is None: raise HTTPException(400, "Não foi possível ler o arquivo")
    sample = text[:5000]
    try: dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
    except csv.Error: dialect = csv.excel; dialect.delimiter = ";"
    rows = list(csv.DictReader(io.StringIO(text), dialect=dialect))
    if not rows: raise HTTPException(400, "Arquivo sem registros")
    normalized = {k.lower().strip(): k for k in rows[0].keys() if k}
    aliases = {
        "code": ["codigo", "código", "cod", "sku"],
        "name": ["produto", "descricao", "descrição", "nome"],
        "stock": ["estoque", "saldo", "quantidade", "qtd"],
        "min": ["minimo", "mínimo", "estoque minimo", "estoque mínimo"],
        "cost": ["custo", "preco custo", "preço custo"],
        "price": ["venda", "preco venda", "preço venda", "valor venda"],
        "category": ["categoria", "grupo"],
        "brand": ["marca", "fabricante"],
    }
    def key_for(kind):
        return next((normalized[a] for a in aliases[kind] if a in normalized), None)
    keys = {k: key_for(k) for k in aliases}
    if not keys["code"] or not keys["name"]:
        raise HTTPException(400, "O CSV precisa ter pelo menos as colunas código e produto/descrição")
    created = updated = ignored = 0
    for row in rows:
        code = str(row.get(keys["code"], "")).strip()
        name = str(row.get(keys["name"], "")).strip()
        if not code or not name: ignored += 1; continue
        data = {
            "name": name,
            "stock": br_decimal(row.get(keys["stock"])) if keys["stock"] else Decimal("0"),
            "minimum_stock": br_decimal(row.get(keys["min"])) if keys["min"] else Decimal("0"),
            "cost": br_decimal(row.get(keys["cost"])) if keys["cost"] else Decimal("0"),
            "price": br_decimal(row.get(keys["price"])) if keys["price"] else Decimal("0"),
            "category": str(row.get(keys["category"], "")).strip() or None if keys["category"] else None,
            "brand": str(row.get(keys["brand"], "")).strip() or None if keys["brand"] else None,
        }
        product = db.scalar(select(Product).where(Product.code == code))
        if product:
            for k, v in data.items(): setattr(product, k, v)
            updated += 1
        else:
            db.add(Product(code=code, **data)); created += 1
    db.commit()
    return {"created": created, "updated": updated, "ignored": ignored, "total": len(rows)}

@app.get("/work-orders")
def list_orders(_: User = Depends(current_user), db: Session = Depends(db_session)):
    rows = db.scalars(select(WorkOrder).order_by(WorkOrder.opened_at.desc())).all()
    return [{"id": o.id, "customer_id": o.customer_id, "vehicle_id": o.vehicle_id, "status": o.status, "complaint": o.complaint, "diagnosis": o.diagnosis, "total": float(o.total), "opened_at": o.opened_at.isoformat()} for o in rows]

@app.post("/work-orders")
def create_order(data: WorkOrderIn, _: User = Depends(current_user), db: Session = Depends(db_session)):
    obj = WorkOrder(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj
