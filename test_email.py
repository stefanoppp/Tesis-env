import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from decouple import config

def test_smtp_connection():
    print("=== Prueba de Configuración SMTP ===")
    
    try:
        # Leer configuración del .env
        email_user = config('EMAIL_HOST_USER')
        email_password = config('EMAIL_HOST_PASSWORD')
        
        print(f"Email usuario: {email_user}")
        print(f"Password configurado: {'Sí' if email_password else 'No'}")
        
        # Configuración SMTP
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        
        print(f"\nConectando a {smtp_server}:{smtp_port}...")
        
        # Crear conexión SMTP
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Habilitar TLS
        
        print("✅ Conexión TLS establecida")
        
        # Autenticar
        server.login(email_user, email_password)
        print("✅ Autenticación exitosa")
        
        # Crear mensaje de prueba
        msg = MIMEMultipart()
        msg['From'] = email_user
        msg['To'] = email_user  # Enviar a nosotros mismos
        msg['Subject'] = "Prueba de configuración SMTP"
        
        body = "Este es un email de prueba para verificar la configuración SMTP."
        msg.attach(MIMEText(body, 'plain'))
        
        # Enviar email
        text = msg.as_string()
        server.sendmail(email_user, email_user, text)
        print("✅ Email enviado exitosamente")
        
        server.quit()
        print("✅ Conexión cerrada correctamente")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"Tipo de error: {type(e).__name__}")
        return False

def test_env_file():
    print("=== Verificación del archivo .env ===")
    try:
        email_user = config('EMAIL_HOST_USER')
        email_password = config('EMAIL_HOST_PASSWORD')
        
        print(f"EMAIL_HOST_USER: {email_user}")
        print(f"EMAIL_HOST_PASSWORD: {'*' * len(email_password) if email_password else 'NO CONFIGURADO'}")
        
        if not email_user or not email_password:
            print("❌ Faltan credenciales en el archivo .env")
            return False
        
        print("✅ Credenciales encontradas en .env")
        return True
        
    except Exception as e:
        print(f"❌ Error leyendo .env: {e}")
        return False

if __name__ == '__main__':
    print("Iniciando pruebas de configuración de email...\n")
    
    # Verificar archivo .env
    env_ok = test_env_file()
    print()
    
    if env_ok:
        # Probar conexión SMTP
        smtp_ok = test_smtp_connection()
        
        if smtp_ok:
            print("\n🎉 Configuración de email funcionando correctamente")
        else:
            print("\n❌ Hay problemas con la configuración SMTP")
    else:
        print("\n❌ Problemas con el archivo .env")