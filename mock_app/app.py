"""
Simulated Company Application — FastAPI server on port 8001.

Provides REST endpoints for:
  - /api/invoices      CRUD
  - /api/vendors       Read
  - /api/payments      Create + List
  - /api/tasks         CRUD
  - / and /ui          Browser-accessible HTML interface

This is the "internal company system" the AI agent interacts with.
Data is stored in memory (resets on restart) with realistic seed data.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="Acme Corp — Internal System", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory data store with realistic seed data
# ---------------------------------------------------------------------------

VENDORS: dict[str, dict] = {
    "v001": {"id": "v001", "name": "Acme Supplies Ltd", "email": "billing@acmesupplies.com", "phone": "+91-9876543210"},
    "v002": {"id": "v002", "name": "TechVision Corp", "email": "accounts@techvision.io", "phone": "+91-9123456780"},
    "v003": {"id": "v003", "name": "Global Logistics Inc", "email": "finance@globallogistics.com", "phone": "+1-555-0192"},
    "v004": {"id": "v004", "name": "Nexus Consulting", "email": "invoices@nexusconsult.in", "phone": "+91-9900112233"},
}

now = datetime.utcnow()

INVOICES: dict[str, dict] = {
    "inv001": {
        "id": "inv001",
        "vendor_id": "v001",
        "company": "Acme Supplies Ltd",
        "invoice_number": "INV-2024-0891",
        "amount": 148500.00,
        "currency": "INR",
        "due_date": (now + timedelta(days=15)).strftime("%Y-%m-%d"),
        "issue_date": (now - timedelta(days=5)).strftime("%Y-%m-%d"),
        "status": "unpaid",
        "description": "Office supplies Q4 2024",
        "line_items": [
            {"item": "Printer Paper A4 (50 reams)", "qty": 50, "rate": 350, "total": 17500},
            {"item": "Toner Cartridges HP", "qty": 10, "rate": 2800, "total": 28000},
            {"item": "Desk Organizers", "qty": 25, "rate": 450, "total": 11250},
            {"item": "Whiteboard Markers (box)", "qty": 30, "rate": 120, "total": 3600},
            {"item": "Ergonomic Chair (Executive)", "qty": 3, "rate": 29050, "total": 87150},
        ],
        "created_at": (now - timedelta(days=5)).isoformat(),
    },
    "inv002": {
        "id": "inv002",
        "vendor_id": "v002",
        "company": "TechVision Corp",
        "invoice_number": "INV-TV-20241105",
        "amount": 320000.00,
        "currency": "INR",
        "due_date": (now + timedelta(days=7)).strftime("%Y-%m-%d"),
        "issue_date": (now - timedelta(days=23)).strftime("%Y-%m-%d"),
        "status": "unpaid",
        "description": "Software development services November 2024",
        "line_items": [
            {"item": "Backend API development (80hrs)", "qty": 80, "rate": 2500, "total": 200000},
            {"item": "Frontend development (40hrs)", "qty": 40, "rate": 2000, "total": 80000},
            {"item": "DevOps setup", "qty": 1, "rate": 40000, "total": 40000},
        ],
        "created_at": (now - timedelta(days=23)).isoformat(),
    },
    "inv003": {
        "id": "inv003",
        "vendor_id": "v003",
        "company": "Global Logistics Inc",
        "invoice_number": "GL-9932-2024",
        "amount": 54200.00,
        "currency": "INR",
        "due_date": (now - timedelta(days=3)).strftime("%Y-%m-%d"),
        "issue_date": (now - timedelta(days=33)).strftime("%Y-%m-%d"),
        "status": "overdue",
        "description": "Freight charges October 2024",
        "line_items": [
            {"item": "Air freight Mumbai-Delhi", "qty": 1, "rate": 28000, "total": 28000},
            {"item": "Last-mile delivery (12 drops)", "qty": 12, "rate": 1850, "total": 22200},
            {"item": "Packaging materials", "qty": 1, "rate": 4000, "total": 4000},
        ],
        "created_at": (now - timedelta(days=33)).isoformat(),
    },
    "inv004": {
        "id": "inv004",
        "vendor_id": "v001",
        "company": "Acme Supplies Ltd",
        "invoice_number": "INV-2024-0756",
        "amount": 67800.00,
        "currency": "INR",
        "due_date": (now - timedelta(days=12)).strftime("%Y-%m-%d"),
        "issue_date": (now - timedelta(days=42)).strftime("%Y-%m-%d"),
        "status": "paid",
        "description": "Office supplies Q3 2024",
        "line_items": [
            {"item": "Notebooks (bulk)", "qty": 100, "rate": 120, "total": 12000},
            {"item": "Pens and stationery kit", "qty": 50, "rate": 250, "total": 12500},
            {"item": "Filing cabinets", "qty": 3, "rate": 14433, "total": 43300},
        ],
        "created_at": (now - timedelta(days=42)).isoformat(),
        "paid_at": (now - timedelta(days=10)).isoformat(),
    },
}

PAYMENTS: dict[str, dict] = {
    "pay001": {
        "id": "pay001",
        "invoice_id": "inv004",
        "vendor_id": "v001",
        "amount": 67800.00,
        "currency": "INR",
        "method": "bank_transfer",
        "reference": "NEFT/20241122/876543",
        "paid_at": (now - timedelta(days=10)).isoformat(),
        "notes": "Q3 payment cleared",
    }
}

TASKS: dict[str, dict] = {
    "task001": {
        "id": "task001",
        "title": "Review TechVision invoice",
        "description": "Verify hours billed match timesheets for November",
        "status": "open",
        "priority": "high",
        "assignee": "finance_team",
        "created_at": (now - timedelta(days=2)).isoformat(),
    },
    "task002": {
        "id": "task002",
        "title": "Follow up Global Logistics overdue payment",
        "description": "Invoice GL-9932-2024 is 3 days overdue",
        "status": "open",
        "priority": "urgent",
        "assignee": "accounts_payable",
        "created_at": now.isoformat(),
    },
}


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class InvoiceCreate(BaseModel):
    vendor_id: Optional[str] = None
    company: str
    invoice_number: str
    amount: float
    currency: str = "INR"
    due_date: str
    issue_date: Optional[str] = None
    status: str = "unpaid"
    description: Optional[str] = None
    line_items: Optional[list] = None


class InvoiceUpdate(BaseModel):
    amount: Optional[float] = None
    due_date: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None


class PaymentCreate(BaseModel):
    invoice_id: str
    amount: float
    currency: str = "INR"
    method: str = "bank_transfer"
    reference: Optional[str] = None
    notes: Optional[str] = None


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    status: str = "open"
    priority: str = "normal"
    assignee: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee: Optional[str] = None


# ---------------------------------------------------------------------------
# Routes — Invoices
# ---------------------------------------------------------------------------

@app.get("/api/invoices")
async def list_invoices(company: Optional[str] = Query(None)):
    invoices = list(INVOICES.values())
    if company:
        company_lower = company.lower()
        invoices = [inv for inv in invoices if company_lower in inv["company"].lower()]
    # Sort by created_at desc (latest first)
    invoices.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"invoices": invoices, "total": len(invoices)}


@app.get("/api/invoices/{invoice_id}")
async def get_invoice(invoice_id: str):
    if invoice_id not in INVOICES:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
    return INVOICES[invoice_id]


@app.post("/api/invoices", status_code=201)
async def create_invoice(data: InvoiceCreate):
    inv_id = f"inv{str(uuid.uuid4().hex[:6])}"
    invoice = {
        "id": inv_id,
        "created_at": datetime.utcnow().isoformat(),
        **data.model_dump(exclude_none=True),
    }
    INVOICES[inv_id] = invoice
    return invoice


@app.put("/api/invoices/{invoice_id}")
async def update_invoice(invoice_id: str, data: InvoiceUpdate):
    if invoice_id not in INVOICES:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
    updates = data.model_dump(exclude_none=True)
    INVOICES[invoice_id].update(updates)
    INVOICES[invoice_id]["updated_at"] = datetime.utcnow().isoformat()
    return INVOICES[invoice_id]


# ---------------------------------------------------------------------------
# Routes — Vendors
# ---------------------------------------------------------------------------

@app.get("/api/vendors")
async def list_vendors():
    return {"vendors": list(VENDORS.values()), "total": len(VENDORS)}


@app.get("/api/vendors/{vendor_id}")
async def get_vendor(vendor_id: str):
    if vendor_id not in VENDORS:
        raise HTTPException(status_code=404, detail=f"Vendor {vendor_id} not found")
    return VENDORS[vendor_id]


# ---------------------------------------------------------------------------
# Routes — Payments
# ---------------------------------------------------------------------------

@app.get("/api/payments")
async def list_payments():
    return {"payments": list(PAYMENTS.values()), "total": len(PAYMENTS)}


@app.post("/api/payments", status_code=201)
async def record_payment(data: PaymentCreate):
    # Validate invoice exists
    if data.invoice_id not in INVOICES:
        raise HTTPException(status_code=404, detail=f"Invoice {data.invoice_id} not found")

    pay_id = f"pay{str(uuid.uuid4().hex[:6])}"
    payment = {
        "id": pay_id,
        "paid_at": datetime.utcnow().isoformat(),
        **data.model_dump(exclude_none=True),
    }
    PAYMENTS[pay_id] = payment

    # Auto-update invoice status
    INVOICES[data.invoice_id]["status"] = "paid"
    INVOICES[data.invoice_id]["paid_at"] = payment["paid_at"]

    return payment


# ---------------------------------------------------------------------------
# Routes — Tasks
# ---------------------------------------------------------------------------

@app.get("/api/tasks")
async def list_tasks():
    return {"tasks": list(TASKS.values()), "total": len(TASKS)}


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return TASKS[task_id]


@app.post("/api/tasks", status_code=201)
async def create_task(data: TaskCreate):
    task_id = f"task{str(uuid.uuid4().hex[:6])}"
    task = {
        "id": task_id,
        "created_at": datetime.utcnow().isoformat(),
        **data.model_dump(exclude_none=True),
    }
    TASKS[task_id] = task
    return task


@app.put("/api/tasks/{task_id}")
async def update_task(task_id: str, data: TaskUpdate):
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    TASKS[task_id].update(data.model_dump(exclude_none=True))
    TASKS[task_id]["updated_at"] = datetime.utcnow().isoformat()
    return TASKS[task_id]


# ---------------------------------------------------------------------------
# Browser-accessible HTML UI
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
@app.get("/ui", response_class=HTMLResponse)
async def ui():
    invoices_html = ""
    for inv in sorted(INVOICES.values(), key=lambda x: x.get("created_at", ""), reverse=True):
        status_color = {"paid": "#22c55e", "unpaid": "#f59e0b", "overdue": "#ef4444"}.get(inv["status"], "#6b7280")
        invoices_html += f"""
        <tr>
          <td>{inv['invoice_number']}</td>
          <td>{inv['company']}</td>
          <td>₹{inv['amount']:,.2f}</td>
          <td>{inv['due_date']}</td>
          <td><span style="color:{status_color};font-weight:600">{inv['status'].upper()}</span></td>
          <td>{inv['id']}</td>
        </tr>"""

    tasks_html = ""
    for t in TASKS.values():
        priority_color = {"urgent": "#ef4444", "high": "#f59e0b", "normal": "#6b7280"}.get(t.get("priority", "normal"), "#6b7280")
        tasks_html += f"""
        <tr>
          <td>{t['id']}</td>
          <td>{t['title']}</td>
          <td><span style="color:{priority_color}">{t.get('priority','normal').upper()}</span></td>
          <td>{t['status']}</td>
          <td>{t.get('assignee','—')}</td>
        </tr>"""

    return HTMLResponse(content=f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Acme Corp — Internal System</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: system-ui, sans-serif; background: #f8fafc; color: #1e293b; }}
    .header {{ background: #1e3a5f; color: white; padding: 16px 32px; display: flex; align-items: center; gap: 12px; }}
    .header h1 {{ font-size: 1.4rem; }}
    .badge {{ background: #22c55e; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; }}
    .container {{ max-width: 1100px; margin: 32px auto; padding: 0 24px; }}
    h2 {{ font-size: 1.1rem; font-weight: 700; margin-bottom: 12px; color: #1e3a5f; }}
    .section {{ background: white; border-radius: 8px; padding: 24px; margin-bottom: 24px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
    th {{ background: #f1f5f9; text-align: left; padding: 10px 12px; border-bottom: 2px solid #e2e8f0; }}
    td {{ padding: 10px 12px; border-bottom: 1px solid #f1f5f9; }}
    tr:hover td {{ background: #f8fafc; }}
    .api-ref {{ font-family: monospace; background: #1e293b; color: #94d2bd; padding: 16px; border-radius: 8px; font-size: 0.82rem; line-height: 1.8; }}
  </style>
</head>
<body>
  <div class="header">
    <h1>🏢 Acme Corp — Internal System</h1>
    <span class="badge">MOCK</span>
    <span style="margin-left:auto;font-size:0.85rem;opacity:0.8">Port 8001 · AI Agent Interface</span>
  </div>
  <div class="container">
    <div class="section">
      <h2>📄 Invoices</h2>
      <table>
        <thead><tr><th>Invoice #</th><th>Company</th><th>Amount</th><th>Due Date</th><th>Status</th><th>ID</th></tr></thead>
        <tbody>{invoices_html}</tbody>
      </table>
    </div>
    <div class="section">
      <h2>✅ Work Tasks</h2>
      <table>
        <thead><tr><th>ID</th><th>Title</th><th>Priority</th><th>Status</th><th>Assignee</th></tr></thead>
        <tbody>{tasks_html}</tbody>
      </table>
    </div>
    <div class="section">
      <h2>🔌 REST API Reference</h2>
      <div class="api-ref">
GET    /api/invoices?company=Acme+Supplies   → list invoices (filter by company)<br>
GET    /api/invoices/:id                     → get invoice details<br>
POST   /api/invoices                         → create invoice<br>
PUT    /api/invoices/:id                     → update invoice<br>
GET    /api/vendors                          → list vendors<br>
GET    /api/vendors/:id                      → get vendor<br>
GET    /api/payments                         → list payments<br>
POST   /api/payments                         → record payment<br>
GET    /api/tasks                            → list tasks<br>
POST   /api/tasks                            → create task<br>
PUT    /api/tasks/:id                        → update task<br>
      </div>
    </div>
  </div>
</body>
</html>
""")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mock_app", "invoices": len(INVOICES), "vendors": len(VENDORS)}
