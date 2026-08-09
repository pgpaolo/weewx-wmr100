# Driver WeeWX irrobustito per WMR100 / WMR88

Driver USB WeeWX per le console Oregon Scientific che espongono il protocollo HID della famiglia WMR100, con un profilo operativo esplicito per **WMR88 e WMR88A**.

La release `3.5.6-gp6` deriva dal driver WeeWX `wmr100.py` 3.5.0 e conserva la mappatura meteorologica originale. Aggiunge recovery USB, validazione dei pacchetti, resincronizzazione del flusso, inizializzazione specifica WMR88 e trace sviluppatore JSONL ruotato.

### Novità 3.5.6-gp6

- Espone come `forecastIcon` il codice di previsione trasmesso nativamente dalla console nel pacchetto pressione `0x46`.
- Non altera `barometer` o `altimeter`: per la famiglia WMR100 restano calcolati da WeeWX `StdWXCalculate`, preservando il comportamento corretto e stabile.
- Mantiene `console_barometer` come dato interno/diagnostico, senza inserirlo negli archivi con un nome semanticamente errato.

- Recupero verificato del raro caso `FF FF FF`: un singolo `0xFF` residuo viene rimosso solo se il frame risultante ha tipo noto, lunghezza corretta e checksum valido.
- Nuovo evento diagnostico `packet_leading_ff_recovered` e relativo contatore.

- I timeout USB isolati restano informativi e non portano più lo stato del driver a `degraded`.
- Lo stato passa a `warning` soltanto al raggiungimento di `timeout_warning_threshold`.
- Alla ripresa della lettura viene emesso l'evento `usb_read_recovered`, con episodio, numero di timeout recuperati e tempi di recovery.
- Sono disponibili contatori cumulativi dedicati agli episodi di timeout e alle recovery automatiche.

> **Stato:** i test automatici del protocollo e del recovery sono superati. È comunque raccomandata una validazione prolungata con una console WMR88/WMR88A reale prima dell'uso non presidiato.

## Console gestite

- **WMR88 / WMR88A:** profilo prioritario; richiesta dati live automatica e watchdog conservativo.
- WMR100 / WMR100N.
- WMR180 / WMR180A.
- WMRS200 quando espone la medesima interfaccia USB HID.

WMR200/WMR200A usa un driver diverso. WMR89/WMR89A non deve essere considerata compatibile soltanto perché condivide sensori radio simili.

## Sensori tipici WMR88/WMR88A

- WGR800 o equivalente per il vento;
- PCR800 o equivalente per la pioggia;
- THGR800 / THGR810 per temperatura e umidità;
- THWR800 per la sola temperatura;
- UVN800 per l'indice UV;
- fino a tre canali remoti nel profilo WMR88.

## Installazione diretta da GitHub — WeeWX 5

Dopo avere pubblicato il repository, sostituire `OWNER` con l'account o l'organizzazione GitHub:

```bash
sudo weectl extension install \
  https://github.com/OWNER/weewx-wmr100-wmr88-hardened/archive/refs/heads/main.zip
```

Clonare il repository e installare, se necessario, la regola USB:

```bash
git clone https://github.com/OWNER/weewx-wmr100-wmr88-hardened.git
cd weewx-wmr100-wmr88-hardened
sudo ./install-udev-rule.sh
```

Configurare la stazione:

```bash
sudo weectl station reconfigure --driver=user.wmr100
```

Usare `WMR88` per il modello europeo/UK oppure `WMR88A` per la variante nordamericana. Riavviare:

```bash
sudo systemctl restart weewx
sudo journalctl -u weewx -n 100 --no-pager
```

## Installazione dal pacchetto ZIP

```bash
unzip weewx-wmr100-wmr88-hardened-3.5.6-gp6.zip
cd weewx-wmr100-wmr88-hardened-3.5.6-gp6
sudo ./install-udev-rule.sh
sudo weectl extension install . --yes
sudo weectl station reconfigure --driver=user.wmr100
sudo systemctl restart weewx
```

In alternativa:

```bash
sudo ./install.sh
```

Lo script installa regola udev ed estensione, ma lascia volutamente interattiva la riconfigurazione della stazione.

## WeeWX 4

```bash
sudo ./install-udev-rule.sh
sudo weewx_extension --install=.
sudo wee_config --reconfigure --driver=user.wmr100 --no-prompt
sudo systemctl restart weewx
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

Il profilo `WMR88`/`WMR88A` applica automaticamente la richiesta dati live e le soglie conservative, salvo override esplicito.

## Perché `archive_interval = 300`

I sensori trasmettono separatamente e con tempi propri. Il termo-igrometro esterno può trasmettere oltre il minuto; un archivio da 60 secondi può quindi non includere ogni volta tutti i tipi di misura. Il driver non replica artificialmente dati vecchi e non trasforma i LOOP parziali in LOOP completi, evitando soprattutto di duplicare l'incremento `rain`.

## Permessi USB

```bash
lsusb -d 0fde:ca01
BUS=$(lsusb -d 0fde:ca01 | awk '{print $2}')
DEV=$(lsusb -d 0fde:ca01 | awk '{print substr($4,1,3)}')
ls -l "/dev/bus/usb/$BUS/$DEV"
```

L'utente del servizio WeeWX deve avere lettura e scrittura. Le installazioni WeeWX 5 tramite pacchetto possono avere già una regola adeguata; in tal caso quella inclusa nel repository è facoltativa.

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
sudo python3 tools/trace-summary.py \
  /var/log/weewx/wmr100-developer-trace.jsonl
```

Lasciare normalmente `developer_trace_raw_reports = false`. Attivarlo solo per catture brevi.

## Verifica

```bash
sudo journalctl -u weewx -f
```

Deve comparire:

```text
WMR100 driver version is 3.5.5-gp5
```

Test offline:

```bash
./scripts/run-tests.sh
```

## Disinstallazione

```bash
sudo weectl extension uninstall wmr100-wmr88-hardened --yes
sudo ./uninstall-udev-rule.sh
sudo systemctl restart weewx
```

## Contenuto del repository

```text
bin/user/wmr100.py          driver WeeWX
install.py                  installer ufficiale delle estensioni WeeWX
examples/                   configurazioni pronte
docs/                       configurazione, collaudo e note di ricerca
util/udev/rules.d/          regola opzionale per i permessi USB
tests/                      test automatici senza console fisica
tools/trace-summary.py      riepilogo del trace JSONL
scripts/build-release.sh    generazione ZIP di release e SHA-256
GITHUB-PUBLISH-IT.md        guida passo passo alla pubblicazione GitHub
```

## Licenza

GNU General Public License versione 3 o successiva. Gli avvisi di copyright del driver WeeWX originale sono mantenuti. Vedere `LICENSE.txt` e `NOTICE.md`.
