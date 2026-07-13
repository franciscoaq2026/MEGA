# Mega-Sena Stats

App web pessoal de análise estatística da Mega-Sena, com geração de jogos
baseada no histórico real de sorteios. **Em construção por etapas** — README
completo chega na etapa final.

> **Aviso:** cada sorteio é independente e aleatório; nenhuma estratégia
> aumenta a chance real de acerto. Este app é exploração de dados e
> entretenimento, não previsão.

## Rodar localmente

Backend (FastAPI, porta 8000):

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
```

Frontend (React + Vite, porta 5173):

```bash
cd frontend
npm install
npm run dev
```

Abra http://localhost:5173 — o Vite encaminha as chamadas `/api` para o
backend automaticamente.
