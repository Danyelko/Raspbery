from picamera2 import Picamera2
from datetime import datetime
import os
import time
import pygame
import numpy as np
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders


SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
ODOSIELATEL_EMAIL = ""  # tu je potrebné vyplniť adresu odosielateľa
ODOSIELATEL_HESLO =""  # tu je potrebné vyplniť heslo aplikácie
PRIJEMCA_EMAIL = ""  # tu je potrebné vyplniť adresu príjemcu

picam2 = Picamera2()
picam2.configure(picam2.create_still_configuration(main={"size": (640, 480)}))  
picam2.start()

pygame.mixer.init()


posledny_email_cas_pohyb = 0
posledny_email_cas_teplota = 0
email_oneskorenie = 60
TEPLOTA_LIMIT = 20

def zaslanie_emailu(typ = "pohyb", teplota = None, obrazok_cesta = None):
    """Odoslanie emailovej notifikácie s UTF-8 kódovaním."""
    global posledny_email_cas_pohyb, posledny_email_cas_teplota
    aktualny_cas = time.time()
    
    if typ == "pohyb":
        if aktualny_cas - posledny_email_cas_pohyb > email_oneskorenie:
            predmet = "Detekcia pohybu"
            telo = "POZOR! Bol zaznamenaný pohyb kamerou Raspberry Pi!"
            posledny_email_cas_pohyb = aktualny_cas 
        else:
            print("Pohyb: Email sa neposiela – čaká na vypršanie časového limitu.")
            return
    
    elif typ == "teplota":
        if aktualny_cas - posledny_email_cas_teplota > email_oneskorenie:
            predmet = "Vysoká teplota!"
            telo = f"POZOR! Teplota prekročila hranicu {TEPLOTA_LIMIT}°C. Aktuálna teplota: {teplota}°C."
            posledny_email_cas_teplota = aktualny_cas
        else:
            print("Teplota: Email sa neposiela – čaká na vypršanie časového limitu.")
            return

    print(f"\033[034m▶ Posielam email: {predmet}\033[0m")

    try:
        msg = MIMEMultipart()
        msg["Subject"] = predmet
        msg["From"] = ODOSIELATEL_EMAIL
        msg["To"] = PRIJEMCA_EMAIL
        
        if obrazok_cesta and os.path.exists(obrazok_cesta): 
            with open(obrazok_cesta, "rb") as prikladany_subor: 
                mime_base = MIMEBase("image", "jpeg") 
                mime_base.set_payload(prikladany_subor.read()) 
                encoders.encode_base64(mime_base)  
                mime_base.add_header("Content-Disposition", f"attachment; filename={os.path.basename(obrazok_cesta)}")  
                msg.attach(mime_base)  
        print(f"Príloha pridaná: {obrazok_cesta}")  


        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(ODOSIELATEL_EMAIL, ODOSIELATEL_HESLO)
            server.sendmail(ODOSIELATEL_EMAIL, PRIJEMCA_EMAIL, msg.as_string())
            print(" Notifikačný email bol úspešne odoslaný!")
            posledny_email_cas = aktualny_cas
        
    except Exception as e:
            print(f"Chyba pri odosielaní emailu: {e}")
            return
        
        
    else:
        print("Email sa neposiela – čaká na vypršanie časového limitu.")


def ziskaj_teplotu():
    """Číta teplotu zo snímača DS18B20"""
    try:
        
        senzor_cesta = "/sys/bus/w1/devices/28-00001059fbbe/w1_slave"
        with open(senzor_cesta, "r") as file:
            riadky = file.readlines()

       
        if "YES" in riadky[0]:
            teplota_data = riadky[1].split("t=")
            if len(teplota_data) > 1:
                teplota = float(teplota_data[1]) / 1000.0 
                return teplota
    except Exception as e:
        print(f"❌ Chyba pri čítaní teploty: {e}")
    return None 


def prehranie_zvuku():
    zvuk_subor = "/home/daniel/alert.mp3"
    if os.path.exists(zvuk_subor):
        if not pygame.mixer.get_busy():  
            zvuk = pygame.mixer.Sound(zvuk_subor)
            zvuk.play()
            print("Zvuková notifikácia sa prehráva!")
        else:
            print("Zvuk už hrá, neprehrávam znova!")
    else:
        print(f"❌ Zvukový súbor {zvuk_subor} neexistuje. Skontroluj cestu.")


def zachyt_snimku():
    casova_peciatka = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    cesta_snimky= f"/home/daniel/obrazky/zachytena_{casova_peciatka}.jpg"

    priecinok = os.path.dirname(cesta_snimky)
    if not os.path.exists(priecinok):
        print(f"Priečinok {priecinok} neexistuje, vytváram ho...")
        os.makedirs(priecinok, exist_ok = True)

    print(f"Zachytávam obrázok: {cesta_snimky}")
    picam2.capture_file(cesta_snimky)
    
    if os.path.exists(cesta_snimky):
        print(f"✅ Obrázok úspešne uložený: {cesta_snimky}")
        return cesta_snimky
    else:
        print(f"❌ Chyba: Obrázok sa neuložil!")
        return None

def pohyb():
    print("Sledujem pohyb...")
    time.sleep(5)

    
    try:
        predosly_snimok = np.array(picam2.capture_array(), dtype=np.int16)
        print(f"Prvá inicializovaná snímka: {predosly_snimok.shape}")  
    except Exception as e:
        print(f"Chyba pri získavaní prvej snímky: {e}")
        return  

    while True:
        try:
            aktualny_snimok = np.array(picam2.capture_array(), dtype=np.int16)
            print(f"Aktuálny snímok: {aktualny_snimok.shape}")  
        except Exception as e:
            print(f"Chyba pri získavaní snímky: {e}")
            continue
        
       
        teplota = ziskaj_teplotu()
        if teplota is not None and teplota > TEPLOTA_LIMIT:
            print(f"\033[1;31m! Vysoká teplota! Aktuálna teplota: {teplota} °C\033[0m")
            
            obrazok_cesta = zachyt_snimku()
            
            zaslanie_emailu(typ="teplota", teplota=teplota, obrazok_cesta=obrazok_cesta if obrazok_cesta else None)

            
            
        
        rozdiel = np.abs(aktualny_snimok - predosly_snimok) ** 2
        uroven_pohybu = rozdiel.sum()
        print(f"Úroveň pohybu: {uroven_pohybu}")  
        
             
        if uroven_pohybu > 5000000:
            print("\033[1;31m Pohyb zistený! Úroveň: {:.2f}\033[0m".format(uroven_pohybu))
            obrazok_cesta = zachyt_snimku()
            zaslanie_emailu(typ="pohyb", obrazok_cesta=obrazok_cesta)

            
            if uroven_pohybu > 10000000:
                prehranie_zvuku()
            else:
                print("Malý pohyb – zvuk sa neprehráva.")
        else:
            print("\033[1;32m ✅ Žiadny pohyb. Úroveň: {:.2f}\033[0m".format(uroven_pohybu))  

        predosly_snimok = aktualny_snimok  
        time.sleep(1)


if __name__ == "__main__":
    try:
        pohyb()
    except KeyboardInterrupt:
        print("Sledovanie pohybu ukončené.")
    finally:
        picam2.stop()
