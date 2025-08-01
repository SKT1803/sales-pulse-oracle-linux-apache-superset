from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import oracledb as cx_Oracle
from fastapi.middleware.cors import CORSMiddleware

# ---- Config from ENV ----
ORACLE_DSN = os.getenv("ORACLE_DSN", "192.168.1.182:1521/testdb")
ORACLE_USER = os.getenv("ORACLE_USER", "superset")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD", "superset123")

# FastAPI App
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # dilersen "http://localhost:8080" ile sınırla
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Oracle Connection Pool ----
try:
    pool = cx_Oracle.create_pool(
        user=ORACLE_USER,
        password=ORACLE_PASSWORD,
        dsn=ORACLE_DSN,
        min=2,
        max=10,
        increment=2
    )
    print("Oracle connection pool created successfully!")
except Exception as e:
    print(f"Oracle pool creation failed: {e}")
    raise

# ---- Models ----
class Order(BaseModel):
    product_id: int
    quantity: int

def get_product_price(product_id: int):
    """Ürün fiyatını döndürür"""
    with pool.acquire() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT PROD_LIST_PRICE FROM SH.PRODUCTS WHERE PROD_ID = :1",
                [product_id]
            )
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Ürün bulunamadı")
            return float(row[0])

@app.post("/add-order")
def add_order(order: Order):
    try:
        with pool.acquire() as conn:
            with conn.cursor() as cursor:

                # Güvenli ORDER_ID
                cursor.execute("SELECT NVL(MAX(ORDER_ID), 0) + 1 FROM OE.ORDERS")
                next_order_id = cursor.fetchone()[0]

                # Bugünün TIME_ID var mı? (SH.TIMES)
                cursor.execute("""
                    SELECT TIME_ID FROM SH.TIMES
                    WHERE TRUNC(TIME_ID) = TRUNC(SYSDATE)
                """)
                r = cursor.fetchone()
                if r:
                    time_id = r[0]
                else:
                    # Yoksa en büyük TIME_ID'yi al (partition hatalarından kaçınmak için)
                    cursor.execute("SELECT MAX(TIME_ID) FROM SH.TIMES")
                    time_id = cursor.fetchone()[0]

                # Ürün fiyatı ve toplam
                price = get_product_price(order.product_id)
                order_total = price * order.quantity
                customer_id = 101

                # OE.ORDERS
                cursor.execute("""
                    INSERT INTO OE.ORDERS (
                        ORDER_ID, ORDER_DATE, ORDER_MODE, CUSTOMER_ID, ORDER_STATUS,
                        ORDER_TOTAL, SALES_REP_ID, PROMOTION_ID
                    ) VALUES (
                        :1, SYSDATE, 'online', :2, 1, :3, NULL, NULL
                    )
                """, [next_order_id, customer_id, order_total])

                # SH.SALES
                cursor.execute("""
                    INSERT INTO SH.SALES (
                        PROD_ID, CUST_ID, TIME_ID, CHANNEL_ID, PROMO_ID,
                        QUANTITY_SOLD, AMOUNT_SOLD
                    ) VALUES (
                        :1, :2, :3, 3, 999, :4, :5
                    )
                """, [order.product_id, customer_id, time_id, order.quantity, order_total])

                conn.commit()
                return {"status": "Sipariş başarıyla eklendi"}

    except Exception as e:
        print(f"ADD ORDER ERROR: {e}")
        raise HTTPException(status_code=500, detail=f"ERROR IN ADD ORDER: {str(e)}")

@app.get("/products")
def get_products():
    with pool.acquire() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT PROD_ID, PROD_NAME, PROD_DESC, PROD_SUBCATEGORY, PROD_LIST_PRICE
                FROM SH.PRODUCTS
                ORDER BY PROD_NAME
            """)
            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "name": row[1],
                    "description": row[2],
                    "subcategory": row[3],
                    "price": float(row[4]) if row[4] else 0.0
                }
                for row in rows
            ]

@app.get("/sales")
def get_sales():
    with pool.acquire() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT PROD_ID, CUST_ID, TIME_ID, QUANTITY_SOLD, AMOUNT_SOLD
                FROM SH.SALES
                ORDER BY TIME_ID DESC, ROWID DESC
                FETCH FIRST 50 ROWS ONLY
            """)
            rows = cursor.fetchall()
            return [
                {
                    "prod_id": row[0],
                    "cust_id": row[1],
                    "time_id": row[2].strftime("%Y-%m-%d"),
                    "quantity": row[3],
                    "amount": float(row[4])
                }
                for row in rows
            ]

@app.get("/ping")
def ping():
    return {"ok": True}
