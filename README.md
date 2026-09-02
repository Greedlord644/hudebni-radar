# Hudební radar

Veřejný přehled relevantních inzerátů z kategorie Hudebníci na Hudebním bazaru. Výběr je zaměřený na zpěváky a zpěvačky hledající projekt v Praze a okolí a na zajímavé moderně-rockové či metalové projekty.

## Automatická aktualizace

GitHub Actions se pokouší každých 5 minut načíst RSS posledních inzerátů, otevře jen potenciálně relevantní detaily a aktualizuje `app/data/ads.json`. Inzeráty starší než 60 dní se při aktualizaci vyřadí. Po každé kontrole se aktuální podoba automaticky publikuje přes GitHub Pages.

Plánované běhy GitHub Actions mohou být při vytížení GitHubu opožděné. Workflow lze kdykoliv spustit také ručně přes záložku **Actions**.

## Lokální spuštění

```bash
npm run install:ci
pip install -r requirements.txt
python scripts/update_ads.py
npm run dev
```

Statický build pro GitHub Pages lze ověřit příkazem `npx next build`; výstup vznikne ve složce `out`.
