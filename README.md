# BK Finance — Sistema de Gestão Financeira e Atividades

**BK Engenharia e Tecnologia** | Python 3.13 + Streamlit + PostgreSQL (Neon)

---

## 🚀 Setup Rápido

### 1. Clonar e instalar dependências

```bash
git clone <repo>
cd bk_finance
pip install -r requirements.txt
```

### 2. Configurar o banco de dados

Edite `.streamlit/secrets.toml`:
```toml
[database]
url = "postgresql://neondb_owner:SUA_SENHA@SEU_HOST/neondb?sslmode=require&channel_binding=require"

[email]
smtp_host = "smtp.gmail.com"
smtp_port = 587
smtp_user = "seu@email.com"
smtp_password = "senha_de_app_gmail"  # Gere em: myaccount.google.com/apppasswords
```

### 3. Executar

```bash
streamlit run app.py
```

O banco de dados é inicializado automaticamente na primeira execução.

---

## 📦 Estrutura do Projeto

```
bk_finance/
├── app.py                    # Entry point principal
├── requirements.txt
├── .streamlit/
│   ├── config.toml           # Tema dark
│   └── secrets.toml          # Credenciais (não commitar!)
├── pages/
│   ├── home.py               # Dashboard principal
│   ├── financas.py           # Finanças (5 abas)
│   └── atividades.py         # Atividades (3 abas)
├── database/
│   ├── connection.py         # Pool de conexão
│   ├── migrations.py         # Criação de tabelas
│   └── queries.py            # Todas as queries SQL
├── components/
│   ├── charts.py             # Biblioteca de gráficos Plotly
│   └── styles.py             # CSS dark theme
└── utils/
    ├── helpers.py            # Formatação e utilitários
    └── notifications.py      # E-mail de alertas
```

---

## 📋 Páginas e Funcionalidades

### 🏠 Home
- KPIs: Contas em atraso, vencendo em 3 dias, a receber, saldo do dia
- Gráfico de barras + linha (entradas/saídas + acumulado — 6 meses)
- Atividades do dia por prioridade
- Metas SMART em andamento
- Orçamento vs Realizado do mês

### 💼 Finanças
**Aba Cadastros:**
- Fornecedores (nome, CNPJ, e-mail, telefone)
- Categorias/Subcategorias (Entrada/Saída/Ambos → Categoria → Subcategoria)
- Bancos (nome, conta, agência, saldo inicial)

**Aba Movimentações:**
- Formulário completo com tipo, categoria, subcategoria, valor, juros, vencimento, status
- Recorrências (Mensal/Diário/Anual, até 24 meses) com pivot grid
- Tabelas Previsto / Realizado / Diferença com totais e saldo acumulado

**Aba Gerencial:**
- Fluxo de caixa com filtro de período e Previsto/Realizado/Ambos
- 2 Pizzas: Previsto vs Realizado por categoria
- DRE (Demonstrativo de Resultado)
- Extrato com exportação Excel

**Aba Metas & Orçamento:**
- Metas SMART com gauge de progresso
- Orçamento mensal editável (24 meses) com comparativo

**Aba Dashboards:**
- KPIs, gráficos combinados, insights automáticos
- Dicas baseadas nos dados (inadimplência, resultado negativo, etc.)
- Exportação HTML para impressão

### 📋 Atividades
**Aba Atividades:**
- Lista hierárquica (atividade + subatividades indentadas)
- Prioridade: Urgente-Urgente / Importante-Urgente / Importante não Urgente / Não importante-Não urgente
- Status com ícone colorido (🟢/🟡/🔴)
- Filtros por prioridade, status e busca

**Aba Plano de Ação (5W2H):**
- O quê? / Por quê? / Quem? / Quando? / Onde? / Como? / Quanto?
- Vinculado a atividades

**Aba Pomodoro:**
- Timer configurável (trabalho + pausa)
- Bip sonoro ao final de cada fase
- Contador de ciclos

---

## ✉️ Notificações por E-mail

O sistema envia automaticamente e-mail para:
- `marcio@bk-engenharia.com`
- `mnknopp@gmail.com`

Quando há contas ou atividades vencendo nos próximos 3 dias.

**Configurar Gmail:** Gere uma "Senha de app" em:
`https://myaccount.google.com/apppasswords`

---

## 🗄️ Banco de Dados (Neon PostgreSQL)

Tabelas criadas automaticamente:
| Tabela | Descrição |
|---|---|
| `suppliers` | Fornecedores |
| `categories` | Categorias financeiras |
| `subcategories` | Subcategorias |
| `banks` | Contas bancárias |
| `transactions` | Movimentações financeiras |
| `goals` | Metas SMART |
| `budget` | Orçamento mensal |
| `activities` | Atividades e subatividades |
| `action_plan` | Plano de ação 5W2H |

---

## 🔐 Segurança

- **Nunca commitar** `.streamlit/secrets.toml` no Git
- Adicionar ao `.gitignore`: `.streamlit/secrets.toml`
- Usar variáveis de ambiente em produção

---

## 📈 Escalabilidade

O sistema foi projetado para escalar:
- Multi-empresa: adicionar coluna `company_id` nas tabelas
- Multi-usuário: adicionar tabela `users` com autenticação
- API REST: expor endpoints FastAPI sobre as queries existentes
- Deploy: Streamlit Cloud, Railway, Render ou VPS

---

*BK Finance v1.0.0 — BK Engenharia e Tecnologia*
