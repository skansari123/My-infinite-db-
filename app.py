import os
import json
import requests
import sys
import psycopg2
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# CORS Middleware: Taaki aapki local HTML file Render backend se connect ho sake
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS,DELETE"
    return response

# PostgreSQL Connection String
DATABASE_URL = "postgres://infinite_db_store_user:TjcxeMT6MTnVpIEhuvpgYSij51TDMrhf@dpg-d91v17jsq97s73duhfd0-a/infinite_db_store"
SECRET_ADMIN_TOKEN = "mean786"

DEFAULT_CONFIG = {
    "active_db": "My_Cloud_Store",
    "databases": {
        "My_Cloud_Store": "my-mug-store-a3284"
    }
}

def init_db():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cluster_config (
            id SERIAL PRIMARY KEY,
            key VARCHAR(50) UNIQUE,
            value TEXT
        );
    """)
    cur.execute("SELECT value FROM cluster_config WHERE key = 'registry';")
    if not cur.fetchone():
        cur.execute("INSERT INTO cluster_config (key, value) VALUES ('registry', %s);", (json.dumps(DEFAULT_CONFIG),))
    conn.commit()
    cur.close()
    conn.close()

def load_db_registry():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT value FROM cluster_config WHERE key = 'registry';")
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return json.loads(row[0])
        return DEFAULT_CONFIG
    except:
        return DEFAULT_CONFIG

def save_system_config(config):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("UPDATE cluster_config SET value = %s WHERE key = 'registry';", (json.dumps(config),))
        conn.commit()
        cur.close()
        conn.close()
    except:
        pass

class FirestoreRESTProvider:
    def __init__(self, db_name, project_id):
        self.db_name = db_name
        self.project_id = project_id
        self.base_url = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents"
        self.TOTAL_FREE_BYTES = 1 * 1024 * 1024 * 1024

    def _estimate_bytes(self, data_list):
        total_bytes = 0
        for item in data_list:
            total_bytes += sys.getsizeof(str(item)) + 180
        return total_bytes

    def get_stats(self):
        try:
            p_res = requests.get(f"{self.base_url}/products", timeout=4).json()
            o_res = requests.get(f"{self.base_url}/orders", timeout=4).json()
            p_docs = p_res.get('documents', [])
            o_docs = o_res.get('documents', [])
            used_bytes = self._estimate_bytes(p_docs) + self._estimate_bytes(o_docs)
            return {
                "total_mb": 1024.0,
                "used_mb": round(used_bytes / (1024 * 1024), 4),
                "free_mb": round(max(0, self.TOTAL_FREE_BYTES - used_bytes) / (1024 * 1024), 4),
                "pct_full": round((used_bytes / self.TOTAL_FREE_BYTES) * 100, 2),
                "docs_count": len(p_docs) + len(o_docs)
            }
        except:
            return {"total_mb": 1024.0, "used_mb": 0.0, "free_mb": 1024.0, "pct_full": 0.0, "docs_count": 0}

    def add_product(self, data):
        payload = {
            "fields": {
                "title": {"stringValue": str(data.get('title', ''))},
                "price": {"stringValue": str(data.get('price', '0'))},
                "desc": {"stringValue": str(data.get('desc', ''))},
                "img_url": {"stringValue": str(data.get('img_url', ''))}
            }
        }
        res = requests.post(f"{self.base_url}/products", json=payload)
        return res.status_code == 200

    def get_all_products(self):
        try:
            res = requests.get(f"{self.base_url}/products", timeout=4).json()
            docs = res.get('documents', [])
            output = []
            for d in docs:
                fields = d.get('fields', {})
                output.append({
                    "id": d.get('name', '').split('/')[-1],
                    "title": fields.get('title', {}).get('stringValue', 'No Title'),
                    "price": fields.get('price', {}).get('stringValue', '0'),
                    "desc": fields.get('desc', {}).get('stringValue', ''),
                    "img_url": fields.get('img_url', {}).get('stringValue', '')
                })
            return output
        except:
            return []

    def delete_product_by_id(self, doc_id):
        res = requests.delete(f"{self.base_url}/products/{doc_id}")
        return res.status_code == 200

    def add_order(self, data):
        payload = {
            "fields": {
                "name": {"stringValue": str(data.get('name', ''))},
                "phone": {"stringValue": str(data.get('phone', ''))},
                "address": {"stringValue": str(data.get('address', ''))},
                "item_title": {"stringValue": str(data.get('item_title', ''))}
            }
        }
        res = requests.post(f"{self.base_url}/orders", json=payload).json()
        return res.get('name', '').split('/')[-1] if 'name' in res else None

    def get_all_orders(self):
        try:
            res = requests.get(f"{self.base_url}/orders", timeout=4).json()
            docs = res.get('documents', [])
            output = []
            for d in docs:
                fields = d.get('fields', {})
                output.append({
                    "id": d.get('name', '').split('/')[-1],
                    "name": fields.get('name', {}).get('stringValue', ''),
                    "phone": fields.get('phone', {}).get('stringValue', ''),
                    "address": fields.get('address', {}).get('stringValue', ''),
                    "item_title": fields.get('item_title', {}).get('stringValue', '')
                })
            return output
        except:
            return []

DATABASES = {}
ACTIVE_DB_KEY = "My_Cloud_Store"

def refresh_database_instances():
    global DATABASES, ACTIVE_DB_KEY
    config = load_db_registry()
    ACTIVE_DB_KEY = config.get("active_db", "My_Cloud_Store")
    DATABASES.clear()
    for name, p_id in config.get("databases", {}).items():
        DATABASES[name] = FirestoreRESTProvider(name, p_id)

init_db()
refresh_database_instances()

# --- 🛍️ PUBLIC CUSTOMER APP (HTML UI INSIDE APP.PY) ---
# Yeh page jab koi aapki Render URL kholega tab dikhega (Customer UI)
CLIENT_UI_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cloud Mega Store</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: sans-serif; }
        body { background: #f4f6f9; padding: 15px; }
        .header { background: #2563eb; color: white; padding: 20px; text-align: center; border-radius: 12px; margin-bottom: 20px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 15px; }
        .card { background: white; padding: 12px; border-radius: 12px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); display: flex; flex-direction: column; justify-content: space-between; }
        .card img { width: 100%; height: 120px; object-fit: cover; border-radius: 8px; margin-bottom: 10px; }
        .card h4 { font-size: 14px; margin-bottom: 5px; color: #333; }
        .card .price { color: #2563eb; font-weight: bold; margin-bottom: 10px; font-size: 14px; }
        .btn-buy { background: #10b981; color: white; border: none; padding: 8px; width: 100%; border-radius: 6px; font-weight: bold; cursor: pointer; }
        
        /* Simple Modal for Checkout */
        .modal { display: none; position: fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); justify-content:center; align-items:center; }
        .modal-body { background: white; padding: 20px; border-radius: 12px; width: 90%; max-width: 400px; }
        .form-control { width: 100%; padding: 10px; margin: 8px 0; border: 1px solid #ccc; border-radius: 6px; }
    </style>
</head>
<body>

    <div class="header">
        <h1>🛍️ Welcome to Cloud Store</h1>
        <p>Direct Database Federated Engine</p>
    </div>

    <div class="grid" id="productGrid">Loading products...</div>

    <!-- Order Modal -->
    <div class="modal" id="orderModal">
        <div class="modal-body">
            <h3 id="modalTitle">Place Order</h3>
            <input type="text" id="custName" class="form-control" placeholder="Your Name">
            <input type="text" id="custPhone" class="form-control" placeholder="Phone Number">
            <input type="text" id="custAddress" class="form-control" placeholder="Delivery Address">
            <button class="btn-buy" onclick="submitOrder()">Confirm Order</button>
            <button class="btn-buy" style="background:#ef4444; margin-top:5px;" onclick="closeModal()">Cancel</button>
        </div>
    </div>

    <script>
        let currentItemTitle = "";

        function loadProducts() {
            fetch('/api/products')
            .then(res => res.json())
            .then(data => {
                let html = '';
                if(!data.products || data.products.length === 0) {
                    document.getElementById('productGrid').innerHTML = "<p>No products available right now.</p>";
                    return;
                }
                data.products.forEach(p => {
                    html += `
                    <div class="card">
                        <img src="${p.img_url || 'https://via.placeholder.com/150'}">
                        <h4>${p.title}</h4>
                        <div class="price">₹${p.price}</div>
                        <button class="btn-buy" onclick="openOrder('${p.title}')">Buy Now</button>
                    </div>`;
                });
                document.getElementById('productGrid').innerHTML = html;
            });
        }

        function openOrder(title) {
            currentItemTitle = title;
            document.getElementById('modalTitle').innerText = "Order: " + title;
            document.getElementById('orderModal').style.display = "flex";
        }
        function closeModal() { document.getElementById('orderModal').style.display = "none"; }

        function submitOrder() {
            const payload = {
                title: currentItemTitle,
                name: document.getElementById('custName').value,
                phone: document.getElementById('custPhone').value,
                address: document.getElementById('custAddress').value
            };
            fetch('/api/place-order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
            .then(res => res.json())
            .then(data => {
                if(data.success) {
                    alert("🎉 Order placed successfully!");
                    closeModal();
                }
            });
        }

        loadProducts();
    </script>
</body>
</html>
"""

@app.route('/')
def public_root():
    return render_template_string(CLIENT_UI_TEMPLATE)

# --- 🔌 API ENDPOINTS ---

@app.route('/api/products', methods=['GET'])
def api_get_products():
    refresh_database_instances()
    aggregated = []
    for key, db_instance in DATABASES.items():
        if db_instance:
            for i in db_instance.get_all_products():
                item = i.copy()
                item['src_node'] = key
                aggregated.append(item)
    return jsonify({"products": aggregated})

@app.route('/api/place-order', methods=['POST'])
def api_place_order():
    refresh_database_instances()
    global ACTIVE_DB_KEY
    req_data = request.get_json() or {}
    payload = {
        "name": req_data.get('name'),
        "phone": req_data.get('phone'),
        "address": req_data.get('address'),
        "item_title": req_data.get('title')
    }
    new_id = DATABASES[ACTIVE_DB_KEY].add_order(payload) if DATABASES.get(ACTIVE_DB_KEY) else None
    return jsonify({"success": True, "order_id": new_id})

# --- SECURE ADMIN API ROUTINGS ---

def verify_token():
    auth_header = request.headers.get("Authorization")
    return auth_header == f"Bearer {SECRET_ADMIN_TOKEN}"

@app.route('/api/admin/dashboard-data', methods=['GET'])
def api_admin_dashboard():
    if not verify_token(): return jsonify({"error": "Unauthorized"}), 401
    refresh_database_instances()
    db_matrix = {k: db.get_stats() for k, db in DATABASES.items() if db}
    aggregated_products = []
    for key, db_instance in DATABASES.items():
        if db_instance:
            for i in db_instance.get_all_products():
                item = i.copy()
                item['src_node'] = key
                aggregated_products.append(item)
    return jsonify({"active_key": ACTIVE_DB_KEY, "dbs": db_matrix, "products": aggregated_products})

@app.route('/api/admin/upload', methods=['POST'])
def api_admin_upload():
    if not verify_token(): return jsonify({"error": "Unauthorized"}), 401
    refresh_database_instances()
    global ACTIVE_DB_KEY
    req_data = request.get_json() or {}
    payload = {"title": req_data.get('title'), "price": req_data.get('price'), "desc": req_data.get('desc', ''), "img_url": req_data.get('img_url', '')}
    if DATABASES.get(ACTIVE_DB_KEY):
        DATABASES[ACTIVE_DB_KEY].add_product(payload)
        return jsonify({"success": True})
    return jsonify({"success": False})

@app.route('/api/admin/delete-product', methods=['DELETE'])
def api_admin_delete():
    if not verify_token(): return jsonify({"error": "Unauthorized"}), 401
    refresh_database_instances()
    target_db = request.args.get('db')
    doc_id = request.args.get('id')
    if target_db in DATABASES and DATABASES[target_db]:
        DATABASES[target_db].delete_product_by_id(doc_id)
        return jsonify({"success": True})
    return jsonify({"success": False})

@app.route('/api/admin/switch-db', methods=['POST'])
def api_admin_switch():
    if not verify_token(): return jsonify({"error": "Unauthorized"}), 401
    config = load_db_registry()
    req_data = request.get_json() or {}
    target = req_data.get('target')
    if target in config.get("databases", {}):
        config["active_db"] = target
        save_system_config(config)
        return jsonify({"success": True})
    return jsonify({"success": False})

@app.route('/api/admin/add-db', methods=['POST'])
def api_admin_add_db():
    if not verify_token(): return jsonify({"error": "Unauthorized"}), 401
    config = load_db_registry()
    req_data = request.get_json() or {}
    db_name = req_data.get('db_name')
    project_id = req_data.get('project_id')
    if db_name and project_id:
        config["databases"][db_name] = project_id
        save_system_config(config)
        return jsonify({"success": True})
    return jsonify({"success": False})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
