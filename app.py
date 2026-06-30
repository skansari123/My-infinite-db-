import os
import json
import requests
import sys
from flask import Flask, render_template_string, request, redirect, url_for, jsonify, flash

app = Flask(__name__)
app.secret_key = "super_secret_session_key_for_toasts"

# Secure Path configuration for Pydroid3 & Render Linux Environment
REGISTRY_FILE = os.path.join(os.path.expanduser("~"), "db_registry_permanent.json")
SECRET_ADMIN_TOKEN = "mean786"

# Default Structure combining databases and persistent active pointer
DEFAULT_CONFIG = {
    "active_db": "My_Cloud_Store",
    "databases": {
        "My_Cloud_Store": "my-mug-store-a3284"
    }
}

def load_db_registry():
    """Loads whole database config along with its persistent active state"""
    if not os.path.exists(REGISTRY_FILE):
        try:
            with open(REGISTRY_FILE, 'w') as f:
                json.dump(DEFAULT_CONFIG, f)
            return DEFAULT_CONFIG
        except:
            return DEFAULT_CONFIG
    try:
        with open(REGISTRY_FILE, 'r') as f:
            config = json.load(f)
            # Integrity check to handle seamless transition
            if "active_db" not in config or "databases" not in config:
                return DEFAULT_CONFIG
            return config
    except:
        return DEFAULT_CONFIG

def save_system_config(config):
    """Saves the complete state registry cleanly"""
    try:
        with open(REGISTRY_FILE, 'w') as f:
            json.dump(config, f)
    except:
        pass

def save_to_db_registry(name, project_id):
    """Adds a new database node without altering the selected active pointer"""
    config = load_db_registry()
    config["databases"][name] = project_id
    save_system_config(config)

class FirestoreRESTProvider:
    def __init__(self, db_name, project_id):
        self.db_name = db_name
        self.project_id = project_id
        self.base_url = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents"
        self.TOTAL_FREE_BYTES = 1 * 1024 * 1024 * 1024  # 1 GB Buffer

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
            free_bytes = max(0, self.TOTAL_FREE_BYTES - used_bytes)
            
            return {
                "total_mb": 1024.0,
                "used_mb": round(used_bytes / (1024 * 1024), 4),
                "free_mb": round(free_bytes / (1024 * 1024), 4),
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

refresh_database_instances()

# --- COMPACT ARCHITECTURAL UI BODY ---
DYNAMIC_UI_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>E-Commerce Engine</title>
    <style>
        :root { --primary: #2563eb; --dark: #0f172a; --bg: #f8fafc; --surface: #ffffff; }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        body { background: var(--bg); color: var(--dark); padding-bottom: 70px; overflow-x: hidden; }
        
        .navbar { background: var(--dark); color: white; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; position: sticky; top:0; z-index: 100; }
        .navbar h2 { font-size: 18px; font-weight: 700; }
        .btn-orders { background: var(--primary); color: white; border: none; padding: 8px 16px; border-radius: 20px; font-weight: 600; cursor: pointer; font-size: 13px; }
        
        .main-container { padding: 15px; max-width: 600px; margin: auto; }
        .product-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 10px; }
        .product-card { background: var(--surface); border-radius: 12px; overflow: hidden; box-shadow: 0 2px 5px rgba(0,0,0,0.05); display: flex; flex-direction: column; position: relative; }
        .product-img { width: 100%; height: 140px; object-fit: cover; background: #e2e8f0; }
        .product-info { padding: 10px; display: flex; flex-direction: column; flex-grow: 1; justify-content: space-between; }
        .product-title { font-size: 14px; font-weight: 600; margin-bottom: 4px; }
        .product-desc { font-size: 11px; color: #64748b; line-height: 1.3; margin-bottom: 8px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
        .product-price { font-size: 15px; font-weight: 700; color: #10b981; margin-bottom: 8px; }
        .btn-buy { background: var(--dark); color: white; border: none; width: 100%; padding: 8px; border-radius: 6px; font-weight: 600; font-size: 12px; cursor: pointer; }

        /* FIXED: STRICT MOBILE VIEWPORT FULLSCREEN MODALS */
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: var(--surface); z-index: 200; overflow-y: auto; }
        .modal.active { display: block; animation: fadeIn 0.15s ease-out; }
        @keyframes fadeIn { from { transform: translateY(15px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
        .modal-header { background: var(--dark); color: white; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 210; }
        .modal-close { font-size: 26px; font-weight: bold; color: #94a3b8; cursor: pointer; }
        .modal-body { padding: 20px; max-width: 600px; margin: auto; }
        .modal-title { font-size: 18px; font-weight: 700; }

        .form-group { margin-bottom: 14px; }
        .form-group label { display: block; font-size: 12px; font-weight: 600; margin-bottom: 5px; color: #475569; }
        .form-control { width: 100%; padding: 11px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px; }
        .btn-submit { background: var(--primary); color: white; border: none; width: 100%; padding: 12px; border-radius: 8px; font-weight: bold; font-size: 14px; cursor: pointer; margin-top: 10px; display: block; text-align: center; text-decoration: none; }

        #toastBox { position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background: #10b981; color: white; padding: 12px 24px; border-radius: 30px; font-weight: 600; font-size: 13px; z-index: 1000; box-shadow: 0 4px 15px rgba(0,0,0,0.15); display: none; text-align: center; min-width: 250px; }

        .order-row { background: #f1f5f9; padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid var(--primary); }
        .admin-dock { position: fixed; bottom: 0; left: 0; width: 100vw; background: var(--dark); padding: 12px; display: flex; justify-content: space-around; align-items: center; border-top: 1px solid #334155; z-index: 150; }
        .dock-item { color: #94a3b8; text-decoration: none; display: flex; flex-direction: column; align-items: center; font-size: 24px; cursor: pointer; background: transparent; border: none; }
        .dock-item span { font-size: 11px; display: block; margin-top: 2px; }
        .storage-node { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px; margin-bottom: 12px; }
        .progress-container { background: #e2e8f0; border-radius: 6px; height: 12px; width: 100%; overflow: hidden; margin: 6px 0; }
        .progress-bar { background: #10b981; height: 100%; }
        .admin-data-card { border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; margin-bottom: 10px; display: flex; gap: 10px; background: white; align-items: center; }
        .admin-card-img { width: 60px; height: 60px; object-fit: cover; border-radius: 6px; background: #e2e8f0; }
        .btn-danger-sm { background: #ef4444; color: white; border: none; padding: 8px 12px; border-radius: 6px; font-size: 11px; cursor: pointer; margin-left: auto; }
    </style>
</head>
<body>

    <div id="toastBox"></div>

    {% if mode == 'public' %}
    <div class="navbar">
        <h2>🛍️ Mobile Mug Shop</h2>
        <button class="btn-orders" onclick="openOrdersModal()">My Orders</button>
    </div>

    <div class="main-container">
        <div class="product-grid">
            {% for p in products %}
            <div class="product-card">
                {% if p.img_url %}
                    <img class="product-img" src="{{ p.img_url }}" alt="Product Image">
                {% else %}
                    <div class="product-img" style="display:flex; align-items:center; justify-content:center; background:#e2e8f0; font-size:12px; color:#64748b;">No Image</div>
                {% endif %}
                <div class="product-info">
                    <div>
                        <div class="product-title">{{ p.title }}</div>
                        <div class="product-desc">{{ p.desc }}</div>
                    </div>
                    <div>
                        <div class="product-price">₹{{ p.price }}</div>
                        <button class="btn-buy" onclick="triggerCheckout('{{ p.title }}')">Buy Now</button>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <div id="checkoutModal" class="modal">
        <div class="modal-header">
            <div class="modal-title">Place Order</div>
            <span class="modal-close" onclick="closeModal('checkoutModal')">&times;</span>
        </div>
        <div class="modal-body">
            <form id="orderForm" onsubmit="submitClientOrder(event)">
                <input type="hidden" id="orderItemTitle">
                <div class="form-group">
                    <label>Selected Item</label>
                    <input type="text" id="orderItemDisplay" class="form-control" readonly style="background:#f1f5f9;">
                </div>
                <div class="form-group">
                    <label>Your Name</label>
                    <input type="text" id="custName" class="form-control" required placeholder="Enter your full name">
                </div>
                <div class="form-group">
                    <label>Phone Number</label>
                    <input type="tel" id="custPhone" class="form-control" required placeholder="Enter mobile number">
                </div>
                <div class="form-group">
                    <label>Delivery Address</label>
                    <textarea id="custAddress" class="form-control" rows="3" required placeholder="Enter complete address"></textarea>
                </div>
                <button type="submit" class="btn-submit">Submit Order</button>
            </form>
        </div>
    </div>

    <div id="historyModal" class="modal">
        <div class="modal-header">
            <div class="modal-title">📦 Order History</div>
            <span class="modal-close" onclick="closeModal('historyModal')">&times;</span>
        </div>
        <div class="modal-body" id="historyLogsContainer">
            <p style="text-align:center; color:#64748b;">Loading System Logs...</p>
        </div>
    </div>

    <script>
        function showToast(msg) {
            const box = document.getElementById('toastBox');
            box.innerText = msg; box.style.display = 'block';
            setTimeout(() => { box.style.display = 'none'; }, 3500);
        }
        function triggerCheckout(title) {
            document.getElementById('orderItemTitle').value = title;
            document.getElementById('orderItemDisplay').value = title;
            document.getElementById('checkoutModal').classList.add('active');
        }
        function closeModal(id) { document.getElementById(id).classList.remove('active'); }
        
        function submitClientOrder(e) {
            e.preventDefault();
            const payload = {
                title: document.getElementById('orderItemTitle').value,
                name: document.getElementById('custName').value,
                phone: document.getElementById('custPhone').value,
                address: document.getElementById('custAddress').value
            };
            fetch('/api/place-order', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            })
            .then(res => res.json())
            .then(data => {
                if(data.success && data.order_id) {
                    let lockedIds = JSON.parse(localStorage.getItem('my_locked_orders') || '[]');
                    lockedIds.push(data.order_id);
                    localStorage.setItem('my_locked_orders', JSON.stringify(lockedIds));
                    document.getElementById('orderForm').reset();
                    closeModal('checkoutModal');
                    showToast("🎉 Order Placed Successfully!");
                    setTimeout(() => { openOrdersModal(); }, 800);
                }
            });
        }

        function openOrdersModal() {
            const rawKeys = localStorage.getItem('my_locked_orders') || '[]';
            fetch('/api/fetch-locked-orders', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ ids: JSON.parse(rawKeys) })
            })
            .then(res => res.json())
            .then(data => {
                const container = document.getElementById('historyLogsContainer');
                if(!data.orders || data.orders.length === 0) {
                    container.innerHTML = `<p style="text-align:center; color:#64748b; padding:20px;">No matching local trace on this terminal browser.</p>`;
                } else {
                    let html = '';
                    data.orders.forEach(o => {
                        html += `
                        <div class="order-row">
                            <h4 style="color:#0f172a;">${o.item_title}</h4>
                            <p style="font-size:12px; margin-top:4px;"><b>Name:</b> ${o.name} | <b>Phone:</b> ${o.phone}</p>
                            <p style="font-size:12px; color:#475569;"><b>Address:</b> ${o.address}</p>
                        </div>`;
                    });
                    container.innerHTML = html;
                }
                document.getElementById('historyModal').classList.add('active');
            });
        }
    </script>

    {% else %}
    <div class="navbar" style="background: #2563eb;">
        <h2>👑 Control Desk App</h2>
        <span style="font-size:11px; background:rgba(255,255,255,0.2); padding:4px 8px; border-radius:10px;">Node: {{ active_key }}</span>
    </div>

    <div class="main-container">
        <div style="background:white; padding:20px; border-radius:12px; box-shadow:0 2px 8px rgba(0,0,0,0.05); margin-top:10px;">
            <h3 style="margin-bottom:15px; font-size:16px;">Add New Product Node</h3>
            <form action="/admin/{{ token }}/upload" method="POST">
                <div class="form-group">
                    <label>Product Name</label>
                    <input type="text" name="title" class="form-control" placeholder="E.g. Premium White Mug" required>
                </div>
                <div class="form-group">
                    <label>Description</label>
                    <textarea name="desc" class="form-control" rows="3" placeholder="Enter product specifications..."></textarea>
                </div>
                <div class="form-group">
                    <label>Price (INR)</label>
                    <input type="number" name="price" class="form-control" placeholder="₹ Amount" required>
                </div>
                <div class="form-group">
                    <label>Product Image URL</label>
                    <input type="url" name="img_url" class="form-control" placeholder="https://image-link.jpg">
                </div>
                <button type="submit" class="btn-submit" style="background:#2563eb;">Submit & Upload Product</button>
            </form>
        </div>
    </div>

    <div class="admin-dock">
        <div class="dock-item" onclick="location.reload()" style="color:white;">🏠<span style="color:white;">Home</span></div>
        <div class="dock-item" onclick="openAdminSettingsEngine()">⚙️<span>Settings</span></div>
    </div>

    <div id="settingsDashboardModal" class="modal">
        <div class="modal-header">
            <div class="modal-title">⚙️ Settings Engine</div>
            <span class="modal-close" onclick="closeModal('settingsDashboardModal')">&times;</span>
        </div>
        <div class="modal-body">
            <button class="btn-submit" style="background:#0f172a; margin-bottom:15px; text-align:left; padding:16px;" onclick="openStoragePreviewModal()">📊 DB Infrastructure Matrix</button>
            <button class="btn-submit" style="background:#0f172a; margin-bottom:15px; text-align:left; padding:16px;" onclick="openUploadedProductsModal()">📦 Uploaded Products Inventory</button>
            <button class="btn-submit" style="background:#0f172a; text-align:left; padding:16px;" onclick="openSwitchDbModal()">🔄 Hot-Swap Cluster Nodes</button>
        </div>
    </div>

    <div id="storagePreviewModal" class="modal">
        <div class="modal-header">
            <div class="modal-title">📊 DB Infrastructure Matrix</div>
            <span class="modal-close" onclick="closeModal('storagePreviewModal')">&times;</span>
        </div>
        <div class="modal-body">
            <div style="background:#f1f5f9; padding:14px; border-radius:8px; margin-bottom:20px;">
                <h4 style="font-size:12px; margin-bottom:8px;">+ Link Up Experimental Cluster Token</h4>
                <form action="/admin/{{ token }}/add-db" method="POST" style="display:flex; gap:6px;">
                    <input type="text" name="db_name" placeholder="Alias" required class="form-control" style="padding:6px; font-size:12px;">
                    <input type="text" name="project_id" placeholder="Project ID" required class="form-control" style="padding:6px; font-size:12px;">
                    <button class="btn-orders" style="border-radius:6px;">Link</button>
                </form>
            </div>
            {% for k, db in dbs.items() %}
                {% if db %}
                {% set stats = db.get_stats() %}
                <div class="storage-node">
                    <div style="display:flex; justify-content:space-between; font-size:13px;">
                        <b>☁️ {{ k }}</b>
                        <span>{{ stats.used_mb }} MB / 1024 MB</span>
                    </div>
                    <div class="progress-container">
                        <div class="progress-bar" style="width: {{ stats.pct_full }}%;"></div>
                    </div>
                    <div style="display:flex; justify-content:space-between; font-size:11px; color:#64748b;">
                        <span>Free: {{ stats.free_mb }} MB</span>
                        <span>Docs count: {{ stats.docs_count }}</span>
                    </div>
                </div>
                {% endif %}
            {% endfor %}
        </div>
    </div>

    <div id="catalogModal" class="modal">
        <div class="modal-header">
            <div class="modal-title">📦 Active Catalog Grid</div>
            <span class="modal-close" onclick="closeModal('catalogModal')">&times;</span>
        </div>
        <div class="modal-body">
            {% for p in products %}
            <div class="admin-data-card">
                {% if p.img_url %}
                    <img class="admin-card-img" src="{{ p.img_url }}">
                {% else %}
                    <div class="admin-card-img" style="display:flex;align-items:center;justify-content:center;font-size:10px;">No Img</div>
                {% endif %}
                <div style="flex-grow: 1; max-width: 60%;">
                    <h4 style="font-size:13px; text-overflow:ellipsis; overflow:hidden; white-space:nowrap;">{{ p.title }}</h4>
                    <p style="font-size:11px; color:#64748b; text-overflow:ellipsis; overflow:hidden; white-space:nowrap;">{{ p.desc }}</p>
                    <span style="font-size:10px; color:#3b82f6; background:#eff6ff; padding:2px 4px; border-radius:4px; display:inline-block; margin-top:4px;">Node: {{ p.src_node }}</span>
                </div>
                <button class="btn-danger-sm" onclick="location.href='/admin/{{ token }}/delete-product?db={{ p.src_node }}&id={{ p.id }}'">Delete</button>
            </div>
            {% endfor %}
        </div>
    </div>

    <div id="switchDbModal" class="modal">
        <div class="modal-header">
            <div class="modal-title">🔄 Hot-Swap Cluster Segments</div>
            <span class="modal-close" onclick="closeModal('switchDbModal')">&times;</span>
        </div>
        <div class="modal-body">
            <form action="/admin/{{ token }}/switch-db" method="POST">
                <div class="form-group">
                    <label>Select Target Active Cluster Node</label>
                    <select name="target" class="form-control">
                        {% for k in dbs.keys() %}
                            <option value="{{ k }}" {% if k == active_key %}selected{% endif %}>{{ k }}</option>
                        {% endfor %}
                    </select>
                </div>
                <button type="submit" class="btn-submit" style="background:#10b981;">Perform Realtime Switch</button>
            </form>
        </div>
    </div>

    <script>
        function showToast(msg) {
            const box = document.getElementById('toastBox');
            box.innerText = msg; box.style.display = 'block';
            setTimeout(() => { box.style.display = 'none'; }, 3500);
        }
        function openAdminSettingsEngine() { document.getElementById('settingsDashboardModal').classList.add('active'); }
        function openStoragePreviewModal() { document.getElementById('storagePreviewModal').classList.add('active'); }
        function openUploadedProductsModal() { document.getElementById('catalogModal').classList.add('active'); }
        function openSwitchDbModal() { document.getElementById('switchDbModal').classList.add('active'); }
        function closeModal(id) { document.getElementById(id).classList.remove('active'); }

        {% with messages = get_flashed_messages() %}
          {% if messages %}{% for message in messages %}showToast("{{ message }}");{% endfor %}{% endif %}
        {% endwith %}
    </script>
    {% endif %}

</body>
</html>
"""

# --- BACKEND SERVER ROUTING ---

@app.route('/')
def public_homepage():
    refresh_database_instances()
    aggregated_products = []
    for key, db_instance in DATABASES.items():
        if db_instance:
            items = db_instance.get_all_products()
            for i in items:
                item_copy = i.copy()
                item_copy['src_node'] = key
                aggregated_products.append(item_copy)
    return render_template_string(DYNAMIC_UI_TEMPLATE, mode='public', products=aggregated_products)

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

@app.route('/api/fetch-locked-orders', methods=['POST'])
def api_fetch_locked_orders():
    refresh_database_instances()
    req_data = request.get_json() or {}
    allowed_ids = req_data.get('ids', [])
    all_orders = []
    for key, db_instance in DATABASES.items():
        if db_instance:
            all_orders.extend(db_instance.get_all_orders())
    filtered_orders = [o for o in all_orders if o['id'] in allowed_ids]
    return jsonify({"orders": filtered_orders})

@app.route('/admin/<token>')
def secure_admin_panel(token):
    if token != SECRET_ADMIN_TOKEN:
        return "<h4>404 Not Found</h4>", 404
    refresh_database_instances()
    global ACTIVE_DB_KEY
    aggregated_products = []
    for key, db_instance in DATABASES.items():
        if db_instance:
            items = db_instance.get_all_products()
            for i in items:
                i_copy = i.copy()
                i_copy['src_node'] = key
                aggregated_products.append(i_copy)
    return render_template_string(DYNAMIC_UI_TEMPLATE, mode='admin', token=token, dbs=DATABASES, active_key=ACTIVE_DB_KEY, products=aggregated_products)

@app.route('/admin/<token>/upload', methods=['POST'])
def secure_upload(token):
    if token != SECRET_ADMIN_TOKEN: return "Unauthorized", 401
    refresh_database_instances()
    global ACTIVE_DB_KEY
    payload = {
        "title": request.form.get('title'),
        "price": request.form.get('price'),
        "desc": request.form.get('desc', ''),
        "img_url": request.form.get('img_url', '')
    }
    if DATABASES.get(ACTIVE_DB_KEY):
        DATABASES[ACTIVE_DB_KEY].add_product(payload)
        flash("🚀 Product Node Published Permanently!")
    return redirect(f"/admin/{SECRET_ADMIN_TOKEN}")

@app.route('/admin/<token>/delete-product')
def secure_delete(token):
    if token != SECRET_ADMIN_TOKEN: return "Unauthorized", 401
    refresh_database_instances()
    target_db = request.args.get('db')
    doc_id = request.args.get('id')
    if target_db in DATABASES and DATABASES[target_db]:
        DATABASES[target_db].delete_product_by_id(doc_id)
        flash("🗑️ Product Removed From Cloud Cluster Node!")
    return redirect(f"/admin/{SECRET_ADMIN_TOKEN}")

@app.route('/admin/<token>/switch-db', methods=['POST'])
def secure_switch_db(token):
    if token != SECRET_ADMIN_TOKEN: return "Unauthorized", 401
    config = load_db_registry()
    target = request.form.get('target')
    if target in config.get("databases", {}):
        config["active_db"] = target
        save_system_config(config)
        flash(f"🔄 Persistent Switch Active to: {target}")
    return redirect(f"/admin/{SECRET_ADMIN_TOKEN}")

@app.route('/admin/<token>/add-db', methods=['POST'])
def secure_add_db(token):
    if token != SECRET_ADMIN_TOKEN: return "Unauthorized", 401
    config = load_db_registry()
    db_name = request.form.get('db_name')
    project_id = request.form.get('project_id')
    if db_name and project_id:
        config["databases"][db_name] = project_id
        save_system_config(config)
        refresh_database_instances()
        flash(f"➕ Permanently Linked Segment: {db_name}")
    return redirect(f"/admin/{SECRET_ADMIN_TOKEN}")

@app.route('/admin')
def blocked_admin(): return "<h4>404 Not Found</h4>", 404

if __name__ == '__main__':
    # Fixed dynamic port binding to perfectly comply with cloud servers like Render
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)), debug=True)
