# Amigão ERP Profissional — Tema Oficial v2

Sistema web para oficina e autopeças com frontend responsivo, API FastAPI, autenticação JWT e banco PostgreSQL.

## Identidade visual aplicada
- Cores inspiradas na Amigão: vermelho, amarelo, preto e branco.
- Tela de login com logo, mascote e saudação “Seja bem-vindo ao Amigão ERP”.
- Dashboard com o Mascote como assistente e alertas de estoque.
- Menu profissional com módulos operacionais e administrativos.

## Módulos funcionais nesta versão
- Login e sessão segura.
- Dashboard com indicadores reais do banco.
- Clientes.
- Veículos.
- Produtos e estoque.
- Importação de produtos por CSV.
- Ordens de serviço.

## Módulos com layout preparado para evolução
Compras, Vendas/Orçamentos, Financeiro, Caixa, Relatórios, Agenda, WhatsApp, Configurações e Usuários.

## Como executar
1. Instale o Docker Desktop.
2. Abra um terminal nesta pasta.
3. Execute:

```bash
docker compose up --build
```

4. Abra `http://localhost:8080`.

Acesso inicial:
- Usuário: `admin`
- Senha: `admin123`

## Segurança
Troque a senha inicial e o valor de `JWT_SECRET` antes de colocar em produção. Para uso público, configure HTTPS, backups automáticos e políticas de permissão por usuário.
