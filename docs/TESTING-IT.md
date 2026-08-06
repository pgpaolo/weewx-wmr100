# Piano di collaudo WMR88/WMR88A

## 1. Backup

```bash
sudo cp -a /etc/weewx/weewx.conf \
  /etc/weewx/weewx.conf.pre-wmr88-gp2
```

Verificare la presenza della console:

```bash
lsusb -d 0fde:ca01
```

## 2. Test del repository

```bash
./scripts/run-tests.sh
```

## 3. Installazione

```bash
sudo ./install-udev-rule.sh
sudo weectl extension install . --yes
sudo weectl station reconfigure --driver=user.wmr100
```

Impostare `model = WMR88` oppure `WMR88A`.

## 4. Primo avvio

```bash
sudo systemctl restart weewx
sudo journalctl -u weewx -f
```

Controllare:

- versione `3.5.2-gp2`;
- assenza di traceback;
- apertura del dispositivo USB;
- invio di inizializzazione e richiesta dati live;
- produzione regolare di LOOP parziali.

## 5. Trace per 24-48 ore

Mantenere:

```ini
developer_trace = true
developer_trace_packets = true
developer_trace_raw_reports = false
```

Riepilogo:

```bash
sudo python3 tools/trace-summary.py \
  /var/log/weewx/wmr100-developer-trace.jsonl
```

Osservare in particolare:

- `usb_read_timeout` isolati;
- `usb_soft_reinitialisation_*`;
- `usb_recovery_*`;
- `packet_checksum_error`;
- `packet_length_error`;
- `unknown_packet`;
- `sensor_channel_outside_model_profile`.

## 6. Cattura avanzata

Attivare `developer_trace_raw_reports = true` soltanto per un periodo breve e ripristinarlo subito a `false`.

Prima di condividere il trace rimuovere coordinate, nomi host, percorsi personali e indirizzi di rete eventualmente presenti nel contesto diagnostico.

## 7. Criteri minimi di accettazione

- nessun arresto del thread di acquisizione;
- nessuna crescita incontrollata dei log;
- recovery USB riuscito quando simulato con disconnessione e riconnessione;
- incremento pioggia non duplicato;
- ricezione coerente di vento, temperatura/umidità, pressione, pioggia e UV disponibili;
- assenza di reset USB frequenti durante i normali intervalli RF.
