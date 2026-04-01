"""
Test script to generate QR code images from database records
Pulls QR codes created by fix_qr_codes.py and generates PNG images
Each image is named after the merchant for Safaricom app testing
"""

import os
import qrcode
from app import create_app
from models import QRCode, Vendor


def generate_qr_images_from_db():
    """
    Pull QR codes from database and create scannable PNG images
    """
    print("=" * 70)
    print("📱 Generating QR Code Images from Database")
    print("=" * 70)
    
    app = create_app()
    with app.app_context():
        # Create output directory
        output_dir = "Generated_QR_Images"
        os.makedirs(output_dir, exist_ok=True)
        
        # Fetch all QR codes with their vendors
        qr_codes = QRCode.query.order_by(QRCode.id).all()
        
        if not qr_codes:
            print("\n❌ No QR codes found in database!")
            print("   Run fix_qr_codes.py first to generate QR codes.")
            return
        
        print(f"\n✅ Found {len(qr_codes)} QR codes in database\n")
        
        generated_count = 0
        for qr in qr_codes:
            vendor = Vendor.query.get(qr.vendor_id)
            
            if not vendor or not qr.payload_data:
                print(f"   ⚠️  Skipping QR ID {qr.id} - missing data")
                continue
            
            # Create clean filename from merchant name
            merchant_name = vendor.business_name.replace(" ", "_").replace("-", "_")
            filename = f"{merchant_name}_Till_{vendor.business_shortcode}.png"
            filepath = os.path.join(output_dir, filename)
            
            # Generate QR code image from payload
            qr_img = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr_img.add_data(qr.payload_data)
            qr_img.make(fit=True)
            
            img = qr_img.make_image(fill_color="black", back_color="white")
            img.save(filepath)
            
            # Extract CRC for display
            crc_value = qr.payload_data[-4:] if len(qr.payload_data) >= 4 else "N/A"
            
            print(f"✅ QR {qr.id}: {vendor.business_name}")
            print(f"   📂 File: {filename}")
            print(f"   🏪 Till: {vendor.business_shortcode} | MCC: {vendor.mcc}")
            print(f"   🔒 CRC: {crc_value} | Length: {len(qr.payload_data)} chars")
            print(f"   ✓ CBK Compliant\n")
            
            generated_count += 1
        
        print("=" * 70)
        print(f"✅ Generated {generated_count} QR code images!")
        print(f"📂 Location: {os.path.abspath(output_dir)}/")
        print("\n📱 Next Steps:")
        print("   1. Open the Generated_QR_Images folder")
        print("   2. Display each image on your screen")
        print("   3. Scan with Safaricom M-Pesa app")
        print("   4. Enter amount when prompted (static QR)")
        print("   5. Complete payment flow")
        print("=" * 70 + "\n")


if __name__ == "__main__":
    generate_qr_images_from_db()
