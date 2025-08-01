"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL;

function App() {
  const [activeTab, setActiveTab] = useState("sales");
  const [sales, setSales] = useState([]);
  const [products, setProducts] = useState([]);

  const [order, setOrder] = useState({
    product_id: "",
    quantity: "",
  });

  const [notification, setNotification] = useState({ message: "", type: "" });
  const [autoRefresh, setAutoRefresh] = useState(true);

  // Satışları çek
  const fetchSales = async () => {
    try {
      const response = await axios.get(`${API_URL}/sales`);
      setSales(response.data);
    } catch (error) {
      console.error("Satışlar alınamadı:", error);
    }
  };

  // Ürünleri çek
  const fetchProducts = async () => {
    try {
      const response = await axios.get(`${API_URL}/products`);
      setProducts(response.data);
    } catch (error) {
      console.error("Ürünler alınamadı:", error);
    }
  };

  // Satışlar sekmesi (auto-refresh dahil)
  useEffect(() => {
    if (activeTab === "sales") {
      fetchSales();
      let interval = null;
      if (autoRefresh) {
        interval = setInterval(fetchSales, 5000);
      }
      return () => {
        if (interval) clearInterval(interval);
      };
    }
  }, [activeTab, autoRefresh]);

  // Ürünler sekmesi
  useEffect(() => {
    if (activeTab === "newOrder") {
      fetchProducts();
    }
  }, [activeTab]);

  // Bildirim
  const showNotification = (message, type = "success") => {
    setNotification({ message, type });
    setTimeout(() => setNotification({ message: "", type: "" }), 3000);
  };

  // Sipariş gönder
  const handleOrderSubmit = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        product_id: Number(order.product_id),
        quantity: Number(order.quantity),
      };

      await axios.post(`${API_URL}/add-order`, payload);

      setOrder({ product_id: "", quantity: "" });
      showNotification("Sipariş başarıyla eklendi (OE.ORDERS + SH.SALES)!");

      // setActiveTab("sales");
    } catch (error) {
      console.error(error);
      showNotification("Sipariş eklenirken hata oluştu.", "error");
    }
  };

  // Sipariş özeti için yardımcı fonksiyonlar
  const getProductName = (productId) => {
    const product = products.find((p) => p.id === productId);
    return product ? product.name : "Bilinmeyen Ürün";
  };

  const getProductPrice = (productId) => {
    const product = products.find((p) => p.id === productId);
    return product ? product.price : 0;
  };

  const calculateTotal = (productId, quantity) => {
    const price = getProductPrice(productId);
    return (price * quantity).toFixed(2);
  };

  return (
    <div className="app">
      {notification.message && (
        <div className={`notification ${notification.type}`}>
          {notification.message}
        </div>
      )}

      <header className="header">
        <h1>Satış & Sipariş Yönetimi</h1>
      </header>

      <div className="tabs">
        <button
          className={`tab ${activeTab === "newOrder" ? "active" : ""}`}
          onClick={() => setActiveTab("newOrder")}
        >
          Yeni Sipariş
        </button>

        <button
          className={`tab ${activeTab === "sales" ? "active" : ""}`}
          onClick={() => setActiveTab("sales")}
        >
          Satışlar
        </button>
      </div>

      <div className="tab-content">
        {activeTab === "sales" && (
          <div className="card">
            <div className="card-header">
              <h2>Satış Listesi (SH.SALES)</h2>

              {/* Renkli Toggle Butonu */}
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
              {sales.length === 0 ? (
                <p className="empty-state">Henüz satış kaydı bulunamadı</p>
              ) : (
                <table className="table">
                  <thead>
                    <tr>
                      <th>Ürün ID</th>
                      <th>Müşteri ID</th>
                      <th>Tarih</th>
                      <th>Adet</th>
                      <th>Tutar</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sales.map((s, i) => (
                      <tr key={i}>
                        <td>{s.prod_id}</td>
                        <td>{s.cust_id}</td>
                        <td>{s.time_id}</td>
                        <td>{s.quantity}</td>
                        <td>{s.amount.toFixed(2)} $</td>
                      </tr>
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

            {products.length === 0 ? (
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
                        {p.name} ({p.subcategory}) - {p.price.toFixed(2)} $
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

                {/* Sipariş Özeti */}
                {order.product_id && order.quantity && (
                  <div className="order-summary">
                    <div className="summary-title">Sipariş Özeti</div>
                    <div className="summary-content">
                      <p>Ürün: {getProductName(Number(order.product_id))}</p>
                      <p>
                        Birim Fiyat:{" "}
                        {getProductPrice(Number(order.product_id)).toFixed(2)} $
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
