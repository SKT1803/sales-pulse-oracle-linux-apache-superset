# OE.ORDERS + OE.ORDER_ITEMS (ürünler OE.PRODUCT_INFORMATION + PRODUCT_DESCRIPTIONS)
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import oracledb as cx_Oracle
import os

# ------------------ Config ------------------
ORACLE_DSN = os.getenv("ORACLE_DSN", "192.168.1.182:1521/testdb")
ORACLE_USER = os.getenv("ORACLE_USER", "superset")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD", "superset123")

# Ürün dil tercihi (PRODUCT_DESCRIPTIONS.LANGUAGE_ID)
PRODUCT_LANG = os.getenv("PRODUCT_LANG", "TR")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # "http://localhost:5173" ile de sınırlanabilir
    allow_credentials=False, # wildcard ile credentials kullanmıyoruz
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------ Oracle Pool ------------------
pool = None

@app.on_event("startup")
def _startup():
    global pool
    try:
        pool = cx_Oracle.create_pool(
            user=ORACLE_USER,
            password=ORACLE_PASSWORD,
            dsn=ORACLE_DSN,
            min=2,
            max=10,
            increment=2,
        )
        print("Oracle connection pool created successfully!")
    except Exception as e:
        print(f"Oracle pool creation failed: {e}")
        pool = None

def acquire_conn():
    if pool is None:
        raise HTTPException(status_code=503, detail="DB pool hazır değil")
    return pool.acquire()

# ------------------ Models ------------------
class Order(BaseModel):
    product_id: int
    quantity: int

# ------------------ Helpers ------------------
def get_product_price(product_id: int, cursor=None) -> float:
    """Ürün fiyatını OE.PRODUCT_INFORMATION'dan döndürür."""
    close_cursor = False
    if cursor is None:
        close_cursor = True
        with acquire_conn() as conn:
            cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT LIST_PRICE FROM OE.PRODUCT_INFORMATION WHERE PRODUCT_ID = :1",
            [product_id],
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Ürün OE.PRODUCT_INFORMATION'da bulunamadı")
        return float(row[0])
    finally:
        if close_cursor:
            cursor.close()

def build_in_clause_binds(prefix: str, values):
    """Oracle için dinamik IN (:id0,:id1,...) ve bind dict üretir."""
    binds = {f"{prefix}{i}": v for i, v in enumerate(values)}
    in_sql = ",".join(f":{prefix}{i}" for i in range(len(values)))
    return in_sql, binds

# ------------------ Endpoints ------------------
@app.get("/ping")
def ping():
    return {"ok": True}

@app.get("/products")
def get_products(lang: str = Query(default=PRODUCT_LANG, description="PRODUCT_DESCRIPTIONS.LANGUAGE_ID")):
    """
    Ürünleri PRODUCT_DESCRIPTIONS ile join ederek getiriyoruz.
    NVARCHAR2/VARCHAR2 uyumsuzluğunu CAST ile gideriliyor.
    """
    with acquire_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                  pi.PRODUCT_ID,
                  CASE
                    WHEN pd.TRANSLATED_NAME IS NOT NULL
                      THEN CAST(pd.TRANSLATED_NAME AS VARCHAR2(4000 CHAR))
                    ELSE pi.PRODUCT_NAME
                  END AS NAME,
                  pi.LIST_PRICE
                FROM OE.PRODUCT_INFORMATION pi
                LEFT JOIN OE.PRODUCT_DESCRIPTIONS pd
                  ON pd.PRODUCT_ID = pi.PRODUCT_ID
                 AND pd.LANGUAGE_ID = :lang
                WHERE pi.LIST_PRICE IS NOT NULL
                ORDER BY NAME
                """,
                {"lang": lang},
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": r[0],
                    "name": r[1],
                    "description": "",
                    "subcategory": "",
                    "price": float(r[2]) if r[2] is not None else 0.0,
                }
                for r in rows
            ]

@app.get("/orders")
def get_orders(lang: str = Query(default=PRODUCT_LANG)):
    """
    Son 50 siparişi döndürür.
    Ek alanlar:
      - items_count   : satır sayısı (ORDER_ITEMS adedi)
      - items_preview : 'Kulaklık x1; Kablo x2' gibi kısa ürün satırı özeti
    """
    with acquire_conn() as conn:
        with conn.cursor() as cursor:
            # Son 50 order
            cursor.execute(
                """
                SELECT ORDER_ID, ORDER_DATE, CUSTOMER_ID, ORDER_STATUS, ORDER_TOTAL
                FROM OE.ORDERS
                ORDER BY ORDER_DATE DESC, ORDER_ID DESC
                FETCH FIRST 50 ROWS ONLY
                """
            )
            order_rows = cursor.fetchall()
            if not order_rows:
                return []

            order_ids = [r[0] for r in order_rows]

            # Bu siparişlerin satırlarını tek seferde çeker
            in_sql, binds = build_in_clause_binds("id", order_ids)
            sql_items = f"""
                SELECT
                  oi.ORDER_ID,
                  oi.LINE_ITEM_ID,
                  oi.PRODUCT_ID,
                  CASE
                    WHEN pd.TRANSLATED_NAME IS NOT NULL
                      THEN CAST(pd.TRANSLATED_NAME AS VARCHAR2(4000 CHAR))
                    ELSE pi.PRODUCT_NAME
                  END AS NAME,
                  oi.UNIT_PRICE,
                  oi.QUANTITY
                FROM OE.ORDER_ITEMS oi
                JOIN OE.PRODUCT_INFORMATION pi ON pi.PRODUCT_ID = oi.PRODUCT_ID
                LEFT JOIN OE.PRODUCT_DESCRIPTIONS pd
                  ON pd.PRODUCT_ID = oi.PRODUCT_ID
                 AND pd.LANGUAGE_ID = :lang
                WHERE oi.ORDER_ID IN ({in_sql})
                ORDER BY oi.ORDER_ID DESC, oi.LINE_ITEM_ID
            """
            binds["lang"] = lang
            cursor.execute(sql_items, binds)
            item_rows = cursor.fetchall()

            # order_id -> items map
            items_by_order = {}
            for r in item_rows:
                oid = r[0]
                items_by_order.setdefault(oid, []).append({
                    "line_item_id": r[1],
                    "product_id": r[2],
                    "name": r[3],
                    "unit_price": float(r[4]),
                    "quantity": int(r[5]),
                    "line_total": float(r[4]) * int(r[5]),
                })

            # çıktı
            out = []
            for r in order_rows:
                oid, odate, cust, status, total = r
                items = items_by_order.get(oid, [])
                preview = "; ".join(f"{it['name']} x{it['quantity']}" for it in items[:4])
                if len(items) > 4:
                    preview += f" (+{len(items)-4} satır)"
                out.append({
                    "order_id": oid,
                    "order_date": odate.strftime("%Y-%m-%d %H:%M:%S") if hasattr(odate, "strftime") else str(odate),
                    "customer_id": cust,
                    "status": status,
                    "total": float(total) if total is not None else 0.0,
                    "items_count": len(items),  
                    "items_preview": preview,       
                })
            return out

@app.get("/order-items")
def get_order_items(order_id: int, lang: str = Query(default=PRODUCT_LANG)):
    """Belirli bir siparişin satırlarını (ORDER_ITEMS) ürün isimleriyle döndürür."""
    with acquire_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                  oi.ORDER_ID,
                  oi.LINE_ITEM_ID,
                  oi.PRODUCT_ID,
                  CASE
                    WHEN pd.TRANSLATED_NAME IS NOT NULL
                      THEN CAST(pd.TRANSLATED_NAME AS VARCHAR2(4000 CHAR))
                    ELSE pi.PRODUCT_NAME
                  END AS NAME,
                  oi.UNIT_PRICE,
                  oi.QUANTITY
                FROM OE.ORDER_ITEMS oi
                JOIN OE.PRODUCT_INFORMATION pi ON pi.PRODUCT_ID = oi.PRODUCT_ID
                LEFT JOIN OE.PRODUCT_DESCRIPTIONS pd
                  ON pd.PRODUCT_ID = oi.PRODUCT_ID
                 AND pd.LANGUAGE_ID = :lang
                WHERE oi.ORDER_ID = :oid
                ORDER BY oi.LINE_ITEM_ID
                """,
                {"oid": order_id, "lang": lang},
            )
            rows = cursor.fetchall()
            return [
                {
                    "order_id": r[0],
                    "line_item_id": r[1],
                    "product_id": r[2],
                    "name": r[3],
                    "unit_price": float(r[4]),
                    "quantity": int(r[5]),
                    "line_total": float(r[4]) * int(r[5]),
                }
                for r in rows
            ]

@app.post("/add-order")
def add_order(order: Order):
    """
    Yeni sipariş ekler:
      - OE.ORDERS (sipariş başlığı)
      - OE.ORDER_ITEMS (sipariş satırı; LINE_ITEM_ID sipariş içinde 1’den başlar)
    """
    with acquire_conn() as conn:
        try:
            with conn.cursor() as cursor:
                # ORDER_ID (dev için). Prod'da sequence kullanıyoruz.
                cursor.execute("SELECT NVL(MAX(ORDER_ID), 0) + 1 FROM OE.ORDERS")
                next_order_id = cursor.fetchone()[0]

                # Ürün fiyatı ve toplam
                price = get_product_price(order.product_id, cursor=cursor)
                order_total = price * order.quantity
                customer_id = 101  # örnek

                # OE.ORDERS
                cursor.execute(
                    """
                    INSERT INTO OE.ORDERS (
                        ORDER_ID, ORDER_DATE, ORDER_MODE, CUSTOMER_ID, ORDER_STATUS,
                        ORDER_TOTAL, SALES_REP_ID, PROMOTION_ID
                    ) VALUES (
                        :1, SYSDATE, 'online', :2, 1, :3, NULL, NULL
                    )
                    """,
                    [next_order_id, customer_id, order_total],
                )

                # LINE_ITEM_ID (aynı sipariş içinde 1'den başlat)
                cursor.execute(
                    """
                    SELECT NVL(MAX(LINE_ITEM_ID), 0) + 1
                    FROM OE.ORDER_ITEMS
                    WHERE ORDER_ID = :1
                    """,
                    [next_order_id],
                )
                line_item_id = cursor.fetchone()[0]

                # OE.ORDER_ITEMS
                cursor.execute(
                    """
                    INSERT INTO OE.ORDER_ITEMS (
                        ORDER_ID, LINE_ITEM_ID, PRODUCT_ID, UNIT_PRICE, QUANTITY
                    ) VALUES (
                        :1, :2, :3, :4, :5
                    )
                    """,
                    [next_order_id, line_item_id, order.product_id, price, order.quantity],
                )

            conn.commit()
            return {"status": "Sipariş ve satır başarıyla eklendi", "order_id": next_order_id}
        except HTTPException:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            print(f"ADD ORDER ERROR: {e}")
            raise HTTPException(status_code=500, detail=f"ERROR IN ADD ORDER: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
