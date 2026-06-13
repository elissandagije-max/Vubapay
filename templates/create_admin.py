import hashlib
import pymysql

# Database connection
conn = pymysql.connect(
    host='localhost',
    user='root',
    password='',
    database='vubapay',
    charset='utf8mb4'
)

cursor = conn.cursor()

# Hash password 'admin123'
hashed_password = hashlib.sha256('admin123'.encode()).hexdigest()
print(f"Password hash: {hashed_password}")

# Check if admin exists
cursor.execute("SELECT * FROM admins WHERE EMAIL = 'admin@vubapay.rw'")
admin = cursor.fetchone()

if admin:
    print("Admin exists, updating password...")
    cursor.execute("UPDATE admins SET PASSWORD = %s WHERE EMAIL = 'admin@vubapay.rw'", (hashed_password,))
else:
    print("Creating new admin...")
    cursor.execute("""
        INSERT INTO admins (NAMES, EMAIL, PHONE_NUMBER, PASSWORD, ROLE) 
        VALUES ('System Administrator', 'admin@vubapay.rw', '0788000999', %s, 'super_admin')
    """, (hashed_password,))

conn.commit()
print("Admin account created/updated successfully!")
print("Email: admin@vubapay.rw")
print("Password: admin123")

cursor.close()
conn.close()