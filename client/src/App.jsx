import { useState, useEffect } from "react";
import axios from "axios";
import "./App.css";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "http://localhost:8000",
});

const fmtMoney = (v) => {
  const n = Number(v);
  return Number.isFinite(n) ? n.toFixed(2) : "0.00";
};

function App() {
  const [activeTab, setActiveTab] = useState("orders");
  const [orders, setOrders] = useState([]);
  const [products, setProducts] = useState([]);

  const [order, setOrder] = useState({ product_id: "", quantity: "" });
  const [notification, setNotification] = useState({ message: "", type: "" });
  const [autoRefresh, setAutoRefresh] = useState(true);

  const [expandedOrderId, setExpandedOrderId] = useState(null);
  const [orderItems, setOrderItems] = useState([]);
  const [itemsLoading, setItemsLoading] = useState(false);

  const fetchOrders = async () => {
    try {
      const { data } = await api.get("/orders"); // dil gerekiyorsa: /orders?lang=TR
      setOrders(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("Siparişler alınamadı:", err);
    }
  };

  const fetchProducts = async () => {
    try {
      const { data } = await api.get("/products"); // /products?lang=TR
      setProducts(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("Ürünler alınamadı:", err);
    }
  };

  const fetchOrderItems = async (orderId) => {
    try {
      setItemsLoading(true);
      const { data } = await api.get("/order-items", {
        params: { order_id: orderId },
      });
      setOrderItems(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("Sipariş satırları alınamadı:", err);
      setOrderItems([]);
    } finally {
      setItemsLoading(false);
    }
  };

  const toggleDetails = async (orderId) => {
    if (expandedOrderId === orderId) {
      setExpandedOrderId(null);
      setOrderItems([]);
      return;
    }
    setExpandedOrderId(orderId);
    await fetchOrderItems(orderId);
  };

  useEffect(() => {
    if (activeTab === "orders") {
      fetchOrders();
      let interval = null;
      if (autoRefresh) interval = setInterval(fetchOrders, 5000);
      return () => interval && clearInterval(interval);
    }
  }, [activeTab, autoRefresh]);

  useEffect(() => {
    if (activeTab === "newOrder") fetchProducts();
  }, [activeTab]);

  const showNotification = (message, type = "success") => {
    setNotification({ message, type });
    setTimeout(() => setNotification({ message: "", type: "" }), 3000);
  };

  const handleOrderSubmit = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        product_id: Number(order.product_id),
        quantity: Number(order.quantity),
      };
      await api.post("/add-order", payload);
      setOrder({ product_id: "", quantity: "" });
      showNotification(
        "Sipariş başarıyla eklendi (OE.ORDERS + OE.ORDER_ITEMS)!"
      );
      // İstersen listeyi hemen tazele
      // setActiveTab("orders");
      // fetchOrders();
    } catch (error) {
      console.error(error);
      showNotification("Sipariş eklenirken hata oluştu.", "error");
    }
  };

  const getProductName = (productId) => {
    const product = products.find((p) => p.id === productId);
    return product ? product.name : "Bilinmeyen Ürün";
  };

  const getProductPrice = (productId) => {
    const product = products.find((p) => p.id === productId);
    return Number(product?.price ?? 0);
  };

  const calculateTotal = (productId, quantity) => {
    const price = getProductPrice(productId);
    const nQty = Number(quantity);
    return fmtMoney(price * (Number.isFinite(nQty) ? nQty : 0));
  };

  return (
    <div className="app">
      {notification.message && (
        <div className={`notification ${notification.type}`}>
          {notification.message}
        </div>
      )}

      <header className="header">
        <h1>Sipariş & Sipariş Yönetimi</h1>
      </header>

      <div className="tabs">
        <button
          className={`tab ${activeTab === "newOrder" ? "active" : ""}`}
          onClick={() => setActiveTab("newOrder")}
        >
          Yeni Sipariş
        </button>

        <button
          className={`tab ${activeTab === "orders" ? "active" : ""}`}
          onClick={() => setActiveTab("orders")}
        >
          Siparişler
        </button>
      </div>

      <div className="tab-content">
        {activeTab === "orders" && (
          <div className="card">
            <div className="card-header">
              <h2>Sipariş Listesi (OE.ORDERS)</h2>
              <button
                className={`btn-toggle ${autoRefresh ? "on" : "off"}`}
                onClick={() => setAutoRefresh(!autoRefresh)}
              >
                {autoRefresh
                  ? "🔄 Otomatik Yenile: AÇIK"
                  : "⏸️ Otomatik Yenile: KAPALI"}
              </button>
            </div>
            <div className="card-content">
              {!orders?.length ? (
                <p className="empty-state">Henüz sipariş kaydı bulunamadı</p>
              ) : (
                <table className="table">
                  <thead>
                    <tr>
                      <th>Sipariş ID</th>
                      <th>Tarih</th>
                      <th>Müşteri ID</th>
                      <th>Durum</th>
                      <th>Toplam</th>
                      <th>Ürünler (Özet)</th>
                      <th>Satır Sayısı</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {orders.map((o, i) => (
                      <>
                        <tr key={o?.order_id ?? i}>
                          <td>{o?.order_id ?? "-"}</td>
                          <td>{o?.order_date ?? "-"}</td>
                          <td>{o?.customer_id ?? "-"}</td>
                          <td>{o?.status ?? "-"}</td>
                          <td>{fmtMoney(o?.total)} $</td>
                          <td
                            style={{
                              maxWidth: 320,
                              whiteSpace: "nowrap",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                            }}
                          >
                            {o?.items_preview || "—"}
                          </td>
                          <td>{o?.items_count ?? 0}</td>
                          <td>
                            <button
                              type="button"
                              className="btn btn-secondary"
                              onClick={() => toggleDetails(o.order_id)}
                            >
                              {expandedOrderId === o.order_id
                                ? "Gizle"
                                : "Detay"}
                            </button>
                          </td>
                        </tr>

                        {expandedOrderId === o.order_id && (
                          <tr className="details-row">
                            <td colSpan={8}>
                              {itemsLoading ? (
                                <div>Satırlar yükleniyor...</div>
                              ) : !orderItems.length ? (
                                <div>Bu siparişte satır yok.</div>
                              ) : (
                                <div className="items-panel">
                                  <table className="table subtable">
                                    <thead>
                                      <tr>
                                        <th>Satır No</th>
                                        <th>Ürün</th>
                                        <th>Birim Fiyat</th>
                                        <th>Adet</th>
                                        <th>Satır Tutarı</th>{" "}
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {orderItems.map((it) => (
                                        <tr key={it.line_item_id}>
                                          <td>{it.line_item_id}</td>
                                          <td>
                                            {it.name} (#{it.product_id})
                                          </td>
                                          <td>{fmtMoney(it.unit_price)} $</td>
                                          <td>{it.quantity}</td>
                                          <td>{fmtMoney(it.line_total)} $</td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              )}
                            </td>
                          </tr>
                        )}
                      </>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}

        {activeTab === "newOrder" && (
          <div className="card">
            <div className="card-header">
              <h2>Yeni Sipariş Oluştur (OE.ORDERS)</h2>
            </div>

            {!products?.length ? (
              <p className="empty-state">Ürün listesi bulunamadı.</p>
            ) : (
              <form onSubmit={handleOrderSubmit} className="form">
                <div className="form-group">
                  <label>Ürün</label>
                  <select
                    value={order.product_id}
                    onChange={(e) =>
                      setOrder({ ...order, product_id: e.target.value })
                    }
                    required
                  >
                    <option value="">Ürün seçin</option>
                    {products.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} {p.subcategory ? `(${p.subcategory})` : ""} -{" "}
                        {fmtMoney(p.price)} $
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label>Miktar</label>
                  <input
                    type="number"
                    min="1"
                    value={order.quantity}
                    onChange={(e) =>
                      setOrder({ ...order, quantity: e.target.value })
                    }
                    required
                  />
                </div>

                {order.product_id && order.quantity && (
                  <div className="order-summary">
                    <div className="summary-title">Sipariş Özeti</div>
                    <div className="summary-content">
                      <p>Ürün: {getProductName(Number(order.product_id))}</p>
                      <p>
                        Birim Fiyat:{" "}
                        {fmtMoney(getProductPrice(Number(order.product_id)))} $
                      </p>
                      <p className="total">
                        Toplam:{" "}
                        {calculateTotal(
                          Number(order.product_id),
                          Number(order.quantity)
                        )}{" "}
                        $
                      </p>
                    </div>
                  </div>
                )}

                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={!order.product_id || !order.quantity}
                >
                  Sipariş Oluştur
                </button>
              </form>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
