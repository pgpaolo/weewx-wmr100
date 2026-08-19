# Gestione e pubblicazione del repository GitHub

Repository pubblico corrente:

```text
https://github.com/pgpaolo/weewx-wmr100
```

Branch predefinito: `main`.

## 1. Flusso consigliato per le modifiche

Non modificare direttamente `main` quando è attiva la protezione del branch.

Creare un branch dedicato:

```bash
git checkout main
git pull
git checkout -b feature/nome-modifica
```

Dopo le modifiche:

```bash
git add .
git commit -m "Descrizione modifica"
git push -u origin feature/nome-modifica
```

Aprire quindi una Pull Request verso `main` e attendere il completamento dei test GitHub Actions.

## 2. GitHub Actions

Il workflow `Tests` deve risultare verde prima del merge.

La CI esegue:

- compilazione sintattica Python;
- test parser e decoder;
- test profili WMR88/WMR88A;
- test recovery USB;
- test installer WeeWX;
- controllo sintassi degli script shell;
- generazione dell'archivio release deterministico.

Per la build di riferimento la CI usa `scripts/run-tests.sh` e `scripts/build-release.sh`.

## 3. Installazione pubblica dal branch main

```bash
sudo weectl extension install \
  https://github.com/pgpaolo/weewx-wmr100/archive/refs/heads/main.zip
```

Successivamente:

```bash
sudo weectl station reconfigure --driver=user.wmr100
sudo systemctl restart weewx
```

## 4. Creazione della release 3.5.6-gp6

Tag previsto:

```text
v3.5.6-gp6
```

Titolo consigliato:

```text
WMR100/WMR88 hardened driver 3.5.6-gp6
```

Per creare il tag da riga di comando:

```bash
git checkout main
git pull
git tag -a v3.5.6-gp6 -m "WMR100/WMR88 hardened driver 3.5.6-gp6"
git push origin v3.5.6-gp6
```

Su GitHub:

1. aprire **Releases**;
2. scegliere **Draft a new release**;
3. selezionare `v3.5.6-gp6`;
4. usare il titolo sopra;
5. copiare le note da `RELEASE-NOTES-3.5.6-gp6.md`;
6. allegare l'archivio ZIP e il relativo SHA-256 prodotti dalla CI o da `scripts/build-release.sh`;
7. pubblicare la release come stabile se i test sono tutti verdi.

## 5. Installazione della release versionata

```bash
sudo weectl extension install \
  https://github.com/pgpaolo/weewx-wmr100/archive/refs/tags/v3.5.6-gp6.zip
```

## 6. File che non devono essere pubblicati

Il `.gitignore` esclude le principali categorie locali, ma prima di ogni push verificare comunque di non includere:

- `weewx.conf` reale;
- password, token o credenziali;
- trace `*.jsonl`;
- file `*.log`;
- URL privati o hostname interni;
- dettagli della rete locale;
- directory di build o ambienti virtuali Python.

## 7. Pulizia branch

Dopo il merge della Pull Request eliminare il branch temporaneo, salvo necessità specifiche di mantenimento.

Il repository dovrebbe normalmente mantenere `main` come unico branch permanente.

## 8. Descrizione breve consigliata

```text
Hardened WeeWX USB driver for Oregon Scientific WMR100/WMR88/WMR88A stations, with staged USB recovery, packet validation and rotating JSONL diagnostics.
```

Topic consigliati:

```text
weewx weather-station oregon-scientific wmr88 wmr88a wmr100 raspberry-pi usb python
```
