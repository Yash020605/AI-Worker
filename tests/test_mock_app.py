"""
Integration tests for the Mock Company App.
These run against the in-process FastAPI TestClient.

Run: pytest tests/test_mock_app.py -v
"""
import pytest
from fastapi.testclient import TestClient
from mock_app.app import app

client = TestClient(app)


class TestInvoices:
    def test_list_all_invoices(self):
        resp = client.get("/api/invoices")
        assert resp.status_code == 200
        data = resp.json()
        assert "invoices" in data
        assert data["total"] >= 4

    def test_list_invoices_filter_by_company(self):
        resp = client.get("/api/invoices", params={"company": "Acme Supplies"})
        assert resp.status_code == 200
        data = resp.json()
        assert all("Acme" in inv["company"] for inv in data["invoices"])

    def test_get_invoice_by_id(self):
        resp = client.get("/api/invoices/inv001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "inv001"
        assert data["company"] == "Acme Supplies Ltd"
        assert data["amount"] == 148500.0

    def test_get_invoice_not_found(self):
        resp = client.get("/api/invoices/inv_fake")
        assert resp.status_code == 404

    def test_create_invoice(self):
        payload = {
            "company": "Test Corp",
            "invoice_number": "TEST-001",
            "amount": 50000.0,
            "due_date": "2025-01-01",
        }
        resp = client.post("/api/invoices", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["company"] == "Test Corp"
        assert "id" in data

    def test_update_invoice_status(self):
        resp = client.put("/api/invoices/inv001", json={"status": "paid"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "paid"
        # reset
        client.put("/api/invoices/inv001", json={"status": "unpaid"})

    def test_invoices_sorted_latest_first(self):
        resp = client.get("/api/invoices")
        invoices = resp.json()["invoices"]
        dates = [inv["created_at"] for inv in invoices]
        assert dates == sorted(dates, reverse=True)


class TestVendors:
    def test_list_vendors(self):
        resp = client.get("/api/vendors")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 4

    def test_get_vendor(self):
        resp = client.get("/api/vendors/v001")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Acme Supplies Ltd"

    def test_vendor_not_found(self):
        resp = client.get("/api/vendors/v999")
        assert resp.status_code == 404


class TestPayments:
    def test_list_payments(self):
        resp = client.get("/api/payments")
        assert resp.status_code == 200

    def test_record_payment(self):
        payload = {
            "invoice_id": "inv002",
            "amount": 320000.0,
            "method": "bank_transfer",
            "reference": "NEFT/TEST/123456",
        }
        resp = client.post("/api/payments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["invoice_id"] == "inv002"
        assert "id" in data

        # Invoice should be marked paid
        inv_resp = client.get("/api/invoices/inv002")
        assert inv_resp.json()["status"] == "paid"

    def test_payment_invalid_invoice(self):
        resp = client.post("/api/payments", json={"invoice_id": "inv_fake", "amount": 100})
        assert resp.status_code == 404


class TestTasks:
    def test_list_tasks(self):
        resp = client.get("/api/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2

    def test_create_task(self):
        payload = {
            "title": "Review test invoice",
            "description": "Automated test task",
            "priority": "high",
        }
        resp = client.post("/api/tasks", json=payload)
        assert resp.status_code == 201
        assert resp.json()["title"] == "Review test invoice"

    def test_update_task(self):
        resp = client.put("/api/tasks/task001", json={"status": "completed"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        # reset
        client.put("/api/tasks/task001", json={"status": "open"})


class TestUI:
    def test_homepage_loads(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Acme Corp" in resp.text

    def test_health_endpoint(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
