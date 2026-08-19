# Driver WeeWX irrobustito per WMR100 / WMR88

Driver USB WeeWX per le console Oregon Scientific che espongono il protocollo HID della famiglia WMR100, con profilo operativo esplicito per **WMR88 / WMR88A**.

Release corrente: **3.5.6-gp6**.

La release conserva la mappatura meteorologica originale e aggiunge recovery USB a stadi, validazione dei pacchetti, resincronizzazione del parser, inizializzazione specifica WMR88 e diagnostica sviluppatore JSONL ruotata.

## Console supportate

- **WMR88 / WMR88A** — profilo prioritario, richiesta dati live automatica e watchdog conservativo;
- WMR100 / WMR100N;
- WMR180 / WMR180A;
- WMRS200 quando espone la stessa interfaccia USB HID WMR100.

**WMR200/WMR200A usa un driver diverso.** WMR89/WMR89A non va considerata compatibile solo perché condivide sensori Oregon Scientific simili.

## Miglioramenti principali

- espone come `forecastIcon` il codice di previsione nativo della console;
- lascia `barometer` e `altimeter` a `StdWXCalculate`;
- valida report HID, lunghezza frame e checksum;
- resincronizza il flusso su framing `FF FF` e recupera il raro residuo `0xFF` solo dopo verifica completa del frame;
- distingue timeout USB ordinari da veri errori I/O;
- reinvia i comandi di inizializzazione prima di una riapertura USB completa;
- può rieseguire enumerazione, claim e inizializzazione USB dopo silenzio prolungato;
- traccia pacchetti malformati, sconosciuti o sospetti senza interrompere l'acquisizione;
- fornisce trace JSONL ruotato e contatori di salute;
- mantiene i LOOP parziali per evitare dati obsoleti e duplicazione della pioggia incrementale.

## Requisiti

- WeeWX 5.x consigliato; supportata anche l'installazione legacy WeeWX 4;
- Python compatibile con la versione WeeWX installata;
- accesso Linux al dispositivo USB `0fde:ca01`;
- dipendenze USB già richieste dal driver WMR100 standard.

## Installazione da GitHub — WeeWX 5

```bash
sudo weectl extension install \
  https://github.com/pgpaolo/weewx-wmr100/archive/refs/heads/main.zip
```

Regola USB opzionale:

```bash
git clone https://github.com/pgpaolo/weewx-wmr100.git
cd weewx-wmr100
sudo ./install-udev-rule.sh
```

Configurazione della stazione:

```bash
sudo weectl station reconfigure --driver=user.wmr100
sudo systemctl restart weewx
sudo journalctl -u weewx -n 100 --no-pager
```

Usare `WMR88` per la console europea/UK oppure `WMR88A` per la variante nordamericana.

## Installazione di una release versionata

```bash
sudo weectl extension install \
  https://github.com/pgpaolo/weewx-wmr100/archive/refs/tags/v3.5.6-gp6.zip
```

## Configurazione consigliata WMR88

```ini
[Station]
    station_type = WMR100

[WMR100]
    driver = user.wmr100
    model = WMR88

    vendor_id = 0x0fde
    product_id = 0xca01
    interface = 0
    IN_endpoint = 0x81

    timeout = 15
    wait_before_retry = 5
    max_tries = 3
    recovery_max_tries = 3

    timeout_warning_threshold = 8
    timeout_reinit_threshold = 12
    timeout_recovery_threshold = 20

    send_data_request = true
    command_delay = 0.05
    max_remote_channels = 3

    strict_packet_lengths = true
    max_packet_length = 64

    developer_trace = true
    developer_trace_path = /var/log/weewx/wmr100-developer-trace.jsonl
    developer_trace_max_bytes = 5242880
    developer_trace_backup_count = 5
    developer_trace_raw_reports = false
    developer_trace_packets = true

    stats_log_interval = 3600

[StdArchive]
    archive_interval = 300
```

## Trace sviluppatore

```bash
sudo install -d -o weewx -g weewx -m 0750 /var/log/weewx
sudo touch /var/log/weewx/wmr100-developer-trace.jsonl
sudo chown weewx:weewx /var/log/weewx/wmr100-developer-trace.jsonl
sudo chmod 0640 /var/log/weewx/wmr100-developer-trace.jsonl
```

Visualizzazione:

```bash
sudo tail -f /var/log/weewx/wmr100-developer-trace.jsonl
```

Riepilogo:

```bash
sudo python3 tools/trace-summary.py /var/log/weewx/wmr100-developer-trace.jsonl
```

Lasciare normalmente `developer_trace_raw_reports = false`.

## Verifica e test

All'avvio deve comparire:

```text
WMR100 driver version is 3.5.6-gp6
```

Suite completa offline:

```bash
./scripts/run-tests.sh
```

GitHub Actions esegue automaticamente la stessa validazione sulle Pull Request e sui push verso `main`.

## Controllo permessi USB

```bash
lsusb -d 0fde:ca01
BUS=$(lsusb -d 0fde:ca01 | awk '{print $2}')
DEV=$(lsusb -d 0fde:ca01 | awk '{print substr($4,1,3)}')
ls -l "/dev/bus/usb/$BUS/$DEV"
```

L'utente del servizio WeeWX deve avere permessi di lettura e scrittura sul dispositivo.

## Note operative importanti

- Gli intervalli RF dei sensori non coincidono con il polling USB.
- I LOOP restano parziali per progetto; WeeWX li accumula per generare gli archivi.
- Non mappare campi diagnostici nello schema archivio senza creare le corrispondenti colonne database.
- Fare sempre una copia di `weewx.conf` prima di modificare la configurazione della stazione.
- Non pubblicare mai `weewx.conf`, trace JSONL, log, credenziali, URL privati o dettagli della rete locale.

## Contenuto del repository

```text
bin/user/wmr100.py          driver WeeWX
install.py                  metadata ExtensionInstaller
examples/                   configurazioni di esempio
util/udev/rules.d/          regola opzionale permessi USB
docs/                       configurazione, collaudo e ricerca
tests/                      test regressivi offline
tools/trace-summary.py      riepilogo trace JSONL
scripts/run-tests.sh        validazione repository
scripts/build-release.sh    generazione archivio release deterministico
```

## Licenza e attribuzioni

GNU General Public License versione 3 o successiva. Gli avvisi di copyright WeeWX originali sono mantenuti nel driver.

Vedere [LICENSE.txt](LICENSE.txt), [NOTICE.md](NOTICE.md), [SECURITY.md](SECURITY.md) e [CONTRIBUTING.md](CONTRIBUTING.md).
