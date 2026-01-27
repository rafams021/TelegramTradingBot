# setup_telegram_qr.py
"""
Script para configurar Telegram con QR Code.

Uso:
    python setup_telegram_qr.py

Este script:
1. Genera un QR code (imagen PNG + ASCII en consola)
2. Espera que escanees el QR desde tu app de Telegram
3. Crea el archivo de sesión tg_session_qr.session
4. El bot puede usarlo automáticamente después
"""
import asyncio
import os
from telethon import TelegramClient
import qrcode

import config as CFG


async def main():
    print("\n" + "="*60)
    print("🤖 TELEGRAM TRADING BOT - QR CODE SETUP")
    print("="*60)
    
    # Verificar si ya existe sesión
    session_file = f"{CFG.SESSION_NAME}.session"
    if os.path.exists(session_file):
        print(f"\n⚠️  Ya existe una sesión: {session_file}")
        response = input("¿Quieres borrarla y crear una nueva? (s/n): ")
        if response.lower() != 's':
            print("❌ Cancelado")
            return
        os.remove(session_file)
        print(f"✅ Sesión anterior borrada")
    
    print("\n📱 Creando cliente de Telegram...")
    client = TelegramClient(
        CFG.SESSION_NAME,
        CFG.API_ID,
        CFG.API_HASH
    )
    
    await client.connect()
    
    if await client.is_user_authorized():
        print("✅ Ya estás autorizado")
        await client.disconnect()
        return
    
    print("\n🔐 Iniciando login con QR Code...")
    print("="*60)
    
    # Solicitar QR code a Telegram
    qr_login = await client.qr_login()
    
    # Guardar imagen del QR
    qr_image_path = "telegram_qr.png"
    
    print("\n📸 Generando QR code...")
    
    # Generar QR code como imagen PNG
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_login.url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(qr_image_path)
    
    print(f"✅ QR Code guardado en: {qr_image_path}")
    print("\n" + "="*60)
    print("📱 INSTRUCCIONES:")
    print("="*60)
    print("1. Abre Telegram en tu teléfono")
    print("2. Ve a Settings → Devices → Link Desktop Device")
    print("3. Escanea el QR code de la imagen 'telegram_qr.png'")
    print("   (O escanea el QR ASCII que aparece abajo)")
    print("\n⏳ Esperando que escanees el QR code...")
    print("   (Timeout: 2 minutos)")
    print("="*60 + "\n")
    
    # Mostrar QR en consola (ASCII art)
    qr_console = qrcode.QRCode()
    qr_console.add_data(qr_login.url)
    qr_console.make()
    qr_console.print_ascii()
    
    print("\n⏳ Esperando escaneo...\n")
    
    # Esperar a que el usuario escanee
    try:
        await qr_login.wait(timeout=120)  # 2 minutos
        print("\n" + "="*60)
        print("✅ ¡LOGIN EXITOSO!")
        print("="*60)
        print(f"\n📄 Sesión creada: {session_file}")
        print("\n🚀 Ahora puedes ejecutar el bot:")
        print("   python main.py")
        print("   O: start_bot.bat")
        print("\n" + "="*60 + "\n")
        
    except TimeoutError:
        print("\n" + "="*60)
        print("❌ TIMEOUT")
        print("="*60)
        print("\nNo escaneaste el QR a tiempo (2 minutos)")
        print("Ejecuta el script de nuevo para reintentar.")
        print("="*60 + "\n")
    
    except Exception as ex:
        print(f"\n❌ Error: {ex}")
    
    finally:
        await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Cancelado por usuario")