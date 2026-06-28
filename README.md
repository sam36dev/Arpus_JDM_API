# ARPUS JDM API

Backend em Python (FastAPI) da loja ARPUS JDM. Responsável por:

- CRUD de produtos (autenticado para admin)
- Autenticação do admin via JWT
- Pedidos e abertura de pacotes — o sorteio de raridade/carta acontece **no servidor**, nunca no frontend

## Rodando localmente

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python seed.py          # popula raridades e cartas
uvicorn app.main:app --reload --port 8000
```

API em `http://localhost:8000`, docs interativas em `http://localhost:8000/docs`.

Banco padrão: SQLite local (`arpus.db`). Pra usar Postgres, defina a env var `DATABASE_URL` (ex.: `postgresql://user:pass@host/db`) — o código não muda, é só troca de connection string via SQLAlchemy.

## Criar o primeiro admin

```bash
curl -X POST http://localhost:8000/admin/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@arpus.com","password":"sua-senha"}'
```

Só funciona uma vez (enquanto não existir nenhum admin). Depois, login normal em `/admin/login`.

## Principais endpoints

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/products` | não | Lista produtos |
| GET | `/products/{id}` | não | Detalhe do produto |
| POST | `/products` | admin | Cria produto |
| PUT | `/products/{id}` | admin | Atualiza produto |
| DELETE | `/products/{id}` | admin | Remove produto |
| GET | `/rarities` | não | Lista raridades e suas chances |
| POST | `/orders` | não | Cria pedido (status pendente) |
| POST | `/orders/{id}/pay` | admin* | Confirma pagamento e sorteia cartas dos pacotes |
| GET | `/orders/{id}/pulls` | não | Lista cartas sorteadas do pedido |

\* `/orders/{id}/pay` é temporário — simula a confirmação de pagamento manualmente. Quando integrarmos um provedor real (Pix/cartão), isso vira um webhook do provedor em vez de uma chamada autenticada por admin.
