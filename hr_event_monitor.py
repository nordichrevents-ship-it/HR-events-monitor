"""
Nordic HR Events — Website Monitor
====================================
Bevakar angivna sajters event-sidor och skickar ett sammanfattningsmail
när nya events hittas sedan senaste körningen.

Setup:
1. pip install requests beautifulsoup4
2. Lägg till ditt Gmail app-lösenord som GitHub Secret med namnet GMAIL_PASSWORD
3. Lägg till dina sajter i listan SITES
4. Kör manuellt första gången för att bygga upp en baseline
5. Schemalägg via GitHub Actions (se monitor.yml)

Hur det fungerar:
- Scriptet hämtar varje sida och extraherar eventtexter
- Jämför med vad som sågs vid senaste körningen (sparas i snapshot_data.json)
- Om något nytt hittas skickas ett sammanfattningsmail
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import time
import hashlib

# ============================================================
# KONFIGURATION — fyll i dina uppgifter här
# ============================================================

import os

EMAIL_FROM = "nordichrevents@gmail.com"
EMAIL_PASSWORD = os.environ.get("GMAIL_PASSWORD")  # Hämtas från GitHub Secret
EMAIL_TO = "nordichrevents@gmail.com"

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# Fil där snapshots sparas mellan körningar
SNAPSHOT_FILE = "snapshot_data.json"

# Sekunder att vänta mellan varje sajt (snäll mot servrarna)
DELAY_BETWEEN_SITES = 2

# ============================================================
# SAJTER ATT BEVAKA
# Lägg till/ta bort sajter här.
# "selector" är CSS-selektor för event-elementen på sidan.
# Lämna selector som None så används hela sidans text.
# ============================================================

SITES = [
    {
        "name": "BG Institute",
        "url": "https://www.bginstitute.se/webbinarier/",
        "selector": None,
    },
    {
        "name": "Human Capital",
        "url": "https://humancapital.se/natverk-insikter/forelasningar-och-utbildningar/",
        "selector": None,
    },
    {
        "name": "HR Föreningen",
        "url": "https://hrforeningen.se/webinar/",
        "selector": None,
        "note": "OBS: Laddar events dynamiskt — kan missa events längre ner på sidan"
    },
    {
        "name": "NOCA",
        "url": "https://www.noca.dk/kommende-aktiviteter/?_cat_temaer=employee-experience-2%2Clearning-and-development%2Cthe-future-of-work-organization%2Cemployee-experience%2Cdiversity-and-inclusion%2Ctalent-aquisition",
        "selector": None,
    },
    {
        "name": "Simployer (norsk)",
        "url": "https://www.simployer.com/no/kunnskapshub/webinar",
        "selector": None,
    },
    {
        "name": "Simployer (svensk)",
        "url": "https://www.simployer.com/sv/kunskapshub/webinar",
        "selector": None,
    },
    {
        "name": "Dansk HR",
        "url": "https://danskhr.dk/arrangementer/",
        "selector": None,
    },
    {
        "name": "HR Norge",
        "url": "https://www.hrnorge.no/arrangementer-og-kurs/arrangementer#/?type=47995&type=47994&type=47996",
        "selector": None,
    },
    {
        "name": "CatalystOne (svensk)",
        "url": "https://www.catalystone.com/sv/resources?type=webinar",
        "selector": None,
    },
    {
        "name": "CatalystOne (norsk)",
        "url": "https://www.catalystone.com/no/resources?type=webinar",
        "selector": None,
    },
    {
        "name": "CatalystOne (dansk)",
        "url": "https://www.catalystone.com/da/resources?type=webinar",
        "selector": None,
    },
    {
        "name": "Sympa (engelska)",
        "url": "https://www.sympa.com/resources/events-and-webinars/",
        "selector": None,
    },
    {
        "name": "Sympa (svenska)",
        "url": "https://www.sympa.com/sv/resurser/event-och-webbinar/",
        "selector": None,
    },
    {
        "name": "Sympa (norska)",
        "url": "https://www.sympa.com/no/eventer-og-webinarer",
        "selector": None,
    },
    {
        "name": "Sympa (finska)",
        "url": "https://www.sympa.com/fi/kirjasto/tapahtumat-ja-webinaarit/",
        "selector": None,
    },
    {
        "name": "Moderskeppet",
        "url": "https://moderskeppet.se/webbinar/",
        "selector": None,
    },
    {
        "name": "Winningtemp (svensk)",
        "url": "https://www.winningtemp.com/sv/webinars",
        "selector": None,
    },
    {
        "name": "Winningtemp (norsk)",
        "url": "https://www.winningtemp.com/no/webinars",
        "selector": None,
    },
    {
        "name": "Azets (norsk)",
        "url": "https://www.azets.com/no-no/ressurser/webinarer",
        "selector": None,
    },
    {
        "name": "Zalaris",
        "url": "https://zalaris.com/resources/events-webinars",
        "selector": None,
    },
    {
        "name": "SD Worx",
        "url": "https://www.sdworx.se/sv-se/event-webinar",
        "selector": None,
    },
    {
        "name": "Heartpace",
        "url": "https://heartpace.com/sv/hr-studio-list-webinars/",
        "selector": None,
    },
    {
        "name": "Publitech",
        "url": "https://publitech.se/kostnadsfria-webbinar",
        "selector": None,
    },
    {
        "name": "Hailey HR",
        "url": "https://haileyhr.com/vi-har-digitala-och-fysiska-events-har-nedan-hittar/",
        "selector": None,
    },
    {
        "name": "Crona",
        "url": "https://crona.se/webbinarier",
        "selector": None,
    },
    {
        "name": "Assessio",
        "url": "https://assessio.com/sv/webinars/",
        "selector": None,
    },
    {
        "name": "Quinyx (svensk events)",
        "url": "https://www.quinyx.com/sv/events",
        "selector": None,
    },
    {
        "name": "Quinyx (svensk webinars)",
        "url": "https://www.quinyx.com/sv/webinars",
        "selector": None,
    },
    {
        "name": "Quinyx (norsk)",
        "url": "https://www.quinyx.com/no/events",
        "selector": None,
    },
    {
        "name": "Quinyx (finska)",
        "url": "https://www.quinyx.com/fi/events",
        "selector": None,
    },
    {
        "name": "Herbert Nathan",
        "url": "https://herbertnathan.com/event/?filter=event_category%3Dlive-webinar%2Cmassa",
        "selector": None,
    },
    {
        "name": "Talentech",
        "url": "https://talentech.com/sv/events-och-utbildning/",
        "selector": None,
    },
    {
        "name": "Kontek",
        "url": "https://kontek.se/sv/event-och-webinar",
        "selector": None,
    },
    {
        "name": "Alva Labs",
        "url": "https://www.alvalabs.io/webinar",
        "selector": None,
    },
    {
        "name": "Netigate (svensk)",
        "url": "https://www.netigate.net/sv/events/",
        "selector": None,
    },
    {
        "name": "Netigate (norsk)",
        "url": "https://www.netigate.net/no/events/",
        "selector": None,
    },
    {
        "name": "Chef.se / Chefakademin",
        "url": "https://chef.se/chefakademin-talks/#webinar",
        "selector": None,
    },
    # Lägg till fler sajter här:
    # {
    #     "name": "Namn på sajt",
    #     "url": "https://sajt.se/events/",
    #     "selector": None,
    # },
]

# ============================================================
# FUNKTIONER
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def fetch_page_text(url, selector=None):
    """Hämtar sidan och returnerar relevant textinnehåll."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Ta bort navigering, header, footer för att minska brus
        for tag in soup.find_all(["nav", "header", "footer", "script", "style"]):
            tag.decompose()

        if selector:
            elements = soup.select(selector)
            text = " | ".join(el.get_text(separator=" ", strip=True) for el in elements)
        else:
            text = soup.get_text(separator=" ", strip=True)

        # Normalisera whitespace
        text = " ".join(text.split())
        return text

    except Exception as e:
        return f"FEL: {e}"


def get_hash(text):
    """Skapar ett fingeravtryck av texten för snabb jämförelse."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def load_snapshots():
    """Laddar tidigare sparade snapshots."""
    if os.path.exists(SNAPSHOT_FILE):
        with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_snapshots(snapshots):
    """Sparar snapshots till fil."""
    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        json.dump(snapshots, f, ensure_ascii=False, indent=2)


def send_email(subject, body_html):
    """Skickar sammanfattningsmail via Outlook SMTP."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    part = MIMEText(body_html, "html", "utf-8")
    msg.attach(part)

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        print("✅ Mail skickat!")
    except Exception as e:
        print(f"❌ Kunde inte skicka mail: {e}")


def build_email_body(changes):
    """Bygger HTML-mailet med alla förändringar."""
    today = datetime.now().strftime("%d %B %Y")

    rows = ""
    for site_name, site_url, note in changes:
        note_html = f"<br><small style='color:#888;'>{note}</small>" if note else ""
        rows += f"""
        <tr>
            <td style="padding: 12px 16px; border-bottom: 1px solid #eee;">
                <strong>{site_name}</strong>{note_html}
            </td>
            <td style="padding: 12px 16px; border-bottom: 1px solid #eee;">
                <a href="{site_url}" style="color: #0066cc;">{site_url}</a>
            </td>
        </tr>
        """

    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto;">
        <div style="background: #1a1a2e; color: white; padding: 20px 24px; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0;">Nordic HR Events — Nya events hittade</h2>
            <p style="margin: 4px 0 0; opacity: 0.7; font-size: 14px;">{today}</p>
        </div>
        <div style="background: #f9f9f9; padding: 16px 24px;">
            <p>Följande sajter verkar ha uppdaterat sin event-sida sedan igår:</p>
        </div>
        <table style="width: 100%; border-collapse: collapse; background: white;">
            <thead>
                <tr style="background: #f0f0f0;">
                    <th style="padding: 10px 16px; text-align: left; font-size: 13px; color: #666;">SAJT</th>
                    <th style="padding: 10px 16px; text-align: left; font-size: 13px; color: #666;">URL</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
        <div style="padding: 16px 24px; font-size: 13px; color: #888; border-top: 1px solid #eee;">
            Klicka på länkarna ovan för att se vad som är nytt. Kontrollera om det är ett HR-relaterat 
            event som ska listas på Nordic HR Events.
        </div>
    </body>
    </html>
    """
    return body


# ============================================================
# HUVUDPROGRAM
# ============================================================

def main():
    print(f"\n🔍 Nordic HR Events Monitor — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    snapshots = load_snapshots()
    changes = []  # Lista med (namn, url, note) för sajter som förändrats

    for site in SITES:
        name = site["name"]
        url = site["url"]
        selector = site.get("selector")
        note = site.get("note", "")

        print(f"Kollar: {name}...", end=" ")

        text = fetch_page_text(url, selector)

        if text.startswith("FEL:"):
            print(f"⚠️  {text}")
            time.sleep(DELAY_BETWEEN_SITES)
            continue

        current_hash = get_hash(text)
        previous_hash = snapshots.get(url, {}).get("hash")

        if previous_hash is None:
            # Första körningen — spara baseline utan att skicka mail
            print("📸 Baseline sparad (första körningen)")
        elif current_hash != previous_hash:
            print("🆕 Förändring hittad!")
            changes.append((name, url, note))
        else:
            print("✓ Ingen förändring")

        # Uppdatera snapshot
        snapshots[url] = {
            "hash": current_hash,
            "last_checked": datetime.now().isoformat(),
            "name": name,
        }

        time.sleep(DELAY_BETWEEN_SITES)

    save_snapshots(snapshots)

    if changes:
        print(f"\n📧 Skickar sammanfattningsmail med {len(changes)} uppdatering(ar)...")
        subject = f"Nordic HR Events — {len(changes)} sajt(er) med nya events"
        body = build_email_body(changes)
        send_email(subject, body)
    else:
        print("\n✅ Inga förändringar hittades idag.")

    print("\nKlart!")


if __name__ == "__main__":
    main()
