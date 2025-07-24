#!/usr/bin/env python3
"""
Check what products are actually stored in the database and being monitored.
"""
import sys
import os
import sqlite3
tetime

def check_database_products():
    """Check what products are in the database."""
    ..")
    
    try:
        # Connect to database
        db_path = os.path.join('data', 
        if not os.path.exists(db_path):
            print(d!")
        rn
        
        conn = sqlite3.connect_path)
        )
        
        # Check products table
        print("\n📊 PRODUCTS TABLE:")
        cursor.execute("""
            SELECT id, url, urld_at 
            FROM products 
            ESC
        """)
        etchall()
        
        print(f"Total products: {len(products)}")
        for i, product in enumerate(products, 1):
            product_id, url, url_type, channel_id, g
            status = "✅ ACTIVE" if is"
            print(f"\n{i}. {status}")
            print(f"   ID: {product_id}")
            print(f"   URL: {url}")
            print(f
        id}")
            print(f"   Interval: {in
            print(f"   Cre
        
        # Check product_status table
        prin
        cursor.execute("""
            SELECT product_id, title, price, stock_status,  
        
            ORDER BY last_checked DESC
            LIMIT 20
        """)
        statuses = cursor.fetchall()
        
        print(f"Rece")
        for 
            product_id, title, price, sto
        "
            print(f"   {i:2d}. {status_emoji} {title[:50]}... -
            print(f"       ID: {product_id} | Checkedd}")
        
        # Check stock_changes table
        print(f"\n📈 RECENT STOCK CHANGES:")
        ""
            SELECT product_id 
            FROM stock_cha
            ORDER BY timesta DESC
            LIMIT 10
        """)
        chanl()
        
        print(f"Recent stock changes: {len(changes)}")
        s, 1):
            product_ange
        "
            print(f"   {i:mp}")
        
        # Check website_
        print(f"\n⏰ WEBSITE I")

        intervals = cursorhall()
               for d main()in__":
    == "__ma__me

if __na")ted!leeck compe ch"✅ Databasprint(   =" * 50)
  "" +nnt("\ pri)
    
   ducts(_prok_databasechec   
    " * 50)
 ("=rintCK")
    p CHEDUCTTABASE PRO️ DA print("🗄"""
    function.Main":
    ""def main()

int_exc()prraceback.        t
acebacktrmport 
        i {e}")r:"❌ Erro    print(f as e:
    tion Excep    except      
ose()
    conn.cl     
   
      ed_by})")(by {creatterval}s omain}: {in  - {d" rint(f    ps:
         in intervaled_byeatl, crvaeromain, int
 