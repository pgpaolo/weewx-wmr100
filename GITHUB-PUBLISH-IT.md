# Pubblicazione del repository su GitHub

Nome repository consigliato:

```text
weewx-wmr100-wmr88-hardened
```

## 1. Preparazione

Estrarre il pacchetto e aprire la directory:

```bash
unzip weewx-wmr100-wmr88-hardened-3.5.2-gp2.zip
cd weewx-wmr100-wmr88-hardened-3.5.2-gp2
```

Nel file `README.md` sostituire tutte le occorrenze di `OWNER` con il proprio nome utente o organizzazione GitHub:

```bash
sed -i 's#OWNER#NOME_UTENTE_GITHUB#g' README.md
```

## 2. Creazione repository

Creare su GitHub un repository pubblico vuoto chiamato:

```text
weewx-wmr100-wmr88-hardened
```

Non inizializzarlo con README, licenza o `.gitignore`, perché questi file sono già inclusi.

## 3. Primo push

```bash
git init -b main
git add .
git commit -m "Initial release 3.5.2-gp2"
git remote add origin \
  https://github.com/NOME_UTENTE_GITHUB/weewx-wmr100-wmr88-hardened.git
git push -u origin main
```

## 4. Tag della release

```bash
git tag -a v3.5.2-gp2 -m "WMR100/WMR88 hardened driver 3.5.2-gp2"
git push origin v3.5.2-gp2
```

## 5. Release GitHub

Nella pagina del repository:

1. aprire **Releases**;
2. scegliere **Draft a new release**;
3. selezionare il tag `v3.5.2-gp2`;
4. titolo: `WMR100/WMR88 hardened driver 3.5.2-gp2`;
5. copiare il contenuto di `RELEASE-NOTES-3.5.2-gp2.md`;
6. allegare:
   - `weewx-wmr100-wmr88-hardened-3.5.2-gp2.zip`;
   - `weewx-wmr100-wmr88-hardened-3.5.2-gp2.zip.sha256`.

## 6. Verifica GitHub Actions

Aprire la scheda **Actions**. Il workflow `Tests` deve eseguire:

- compilazione Python;
- test del parser e dei decoder;
- test dei profili WMR88/WMR88A;
- test del recovery USB;
- test dell'installer WeeWX;
- generazione dell'archivio di release.

## 7. Comando di installazione pubblico

Dopo la pubblicazione, il comando da inserire nella descrizione del repository è:

```bash
sudo weectl extension install \
  https://github.com/NOME_UTENTE_GITHUB/weewx-wmr100-wmr88-hardened/archive/refs/heads/main.zip
```

Per una release versionata:

```bash
sudo weectl extension install \
  https://github.com/NOME_UTENTE_GITHUB/weewx-wmr100-wmr88-hardened/archive/refs/tags/v3.5.2-gp2.zip
```

Successivamente:

```bash
sudo weectl station reconfigure --driver=user.wmr100
sudo systemctl restart weewx
```

## 8. Descrizione breve consigliata

```text
Hardened WeeWX USB driver for Oregon Scientific WMR100/WMR88/WMR88A stations, with staged USB recovery, packet validation and rotating JSONL diagnostics.
```

Topic GitHub consigliati:

```text
weewx weather-station oregon-scientific wmr88 wmr88a wmr100 raspberry-pi usb python
```
