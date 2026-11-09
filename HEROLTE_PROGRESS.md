# HEROLTE (Galaxy S7 SM-G930F, Exynos 8890): progreso

Registrar por separado: compilación, marcadores recuperados, lo que se ve en
pantalla y comportamiento de iOS. Plan y mapa de hardware en
`docs/herolte-bringup.md`.

## 2026-10-20

- Dispositivo: SM-G930F, bootloader desbloqueado, TWRP instalado.
- `shim/herolte/probe.S` + `probe.c` compilados con Arm GNU Toolchain 14.2.rel1
  (`aarch64-none-elf`): Image de 10.784 bytes, solo relocaciones PC-relativas
  (ADR_PREL_PG_HI21, ADD_ABS_LO12_NC, CALL26), sin llamadas a librería.
  **Solo compilación**; no se ejecutó en el teléfono.
- `tools/herolte-pack-boot.py` probado con una imagen BOOT sintética
  (página de 2048, DTBH v2 con chip 8890): conserva DTBH y ramdisk, copia
  `text_offset`/flags del kernel de stock, recalcula el SHA-1 del header.
  Todavía no se probó con el BOOT real del S7.
- BOOT del teléfono (custom ROM, no stock), leído con `dd` desde TWRP:
  partición de 41.943.040 bytes, página 2048, kernel arm64 sin comprimir de
  38 MB con `text_offset=0x80000`, DTBH v2 con 3 DTB Exynos 8890
  (hw_rev 4–7, 8, 9). DTB: RAM `0x80000000+0x7e400000` y `0x880000000+2G`,
  initrd en `0x82000000`, reservas TIMA `0xb1000000`, ION desde
  `0xc0000000`, módem `0xf0000000`. `0xe2a00000` cae en un hueco libre.
- `probe-boot.img` armado desde ese BOOT (1.495.056 bytes).
- **Primera prueba en el teléfono (reporte del usuario):** el probe muestra
  texto blanco sobre el logo y la cuenta "TWRP EN 60 S"; al terminar, el
  teléfono reinicia solo a TWRP. Prueba que S-Boot ejecuta nuestro Image
  (header arm64 + DTBH correctos), que el framebuffer `0xe2a00000` con el HW
  trigger de DECON_F funciona, que CNTPCT avanza y que el reinicio a
  recovery por PMU `0x105c0000` (INFORM2/INFORM3/SWRESET) funciona.
- **Foto del probe:** EL 1; SCTLR `0x30c5183e` (MMU off); FDT `0x8a000000`;
  IMAGE `0x800bc000`; MIDR `0x410fd034` (Cortex-A53 r0p4); MPIDR
  `0x80000100`; MMFR0 `0x1122` (sin 16 KiB); PFR0 `0x2222`; ISAR0 `0x11120`
  (AES/SHA1/SHA2/CRC32, **sin LSE**); CNTFRQ **0** (como el A5: frecuencia
  desde el ADT, 26 MHz); DECON trigger previo `0x12b0`; initrd
  `0x89000000..0x890dbf7e` (el ramdisk de la ROM).
- Consecuencia: entre initrd y FDT hay 16 MiB, poco para el payload de XNU.
  `xnu_boot` ahora busca el payload pegado a su Image
  (`herolte-pack-boot.py --append`) y usa el initrd solo como alternativa.
- Serie de parches normalizada sobre `xnu-8796.141.3` (ver
  `docs/herolte-bringup.md`): 123 parches aplican con `git apply` simple,
  incluido `0200-herolte-board-target`. 12 movidos a `xnu/patches-pending/`
  (los 10 rotos m?s `0133`/`0134` de GPU del A5, publicados despu?s).
  **El kernel HEROLTE todavía no se compiló**: Actions pendiente.
- `shim/herolte/xnu_boot` (loader) y `tools/mkadt_herolte.py` escritos y
  compilados/ejecutados localmente; sin prueba en el teléfono.
- `0106`/`0107` reescritos como `0201-herolte-amfi-bridge` y
  `0202-herolte-4k-unsigned-dyld-cache`; 125 parches aplican en orden.
- **Primer kernel HEROLTE compilado en Actions** (fork `wardevsa/ios-a5xelte`,
  rama `herolte`, run 39477885586, commit fb6194b): artefacto `xnu-kernel`
  de 61 MB. El chequeo de LSE encontró una sola coincidencia, dentro de
  `K256` (constantes de SHA-256 en `__TEXT`), es decir, datos: el código del
  kernel no tiene atómicas LSE. El chequeo ahora ignora `K256`.
- Actions publica los errores de compilación como anotaciones públicas
  (los logs requieren sesión de GitHub).
- **Primer arranque de XNU en el S7** (`xnu-boot.img`: loader + payload
  pegado de 16.474.720 bytes; kernel sha256 `61a9dd49…ca5d`, cmdline
  `debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam -noprogress`).
  Foto del usuario: consola de XNU en el framebuffer con VM bootstrap,
  zone_init, firehose, scheduler, KDP serial, `iBoot version: herolte-entry`,
  `SWEET PRNG`, `A5XELTE pthread: libpthread-514.100.2 registered`,
  `SWEET AMFI: built-in interface registered`, platform expert iniciado.
  Pánico en `SweetCPU.cpp:86`: `unsupported topology cpu=0 mpidr=0x100
  count=1` (el chequeo esperaba MPIDR 0 del A5).
- `0203-herolte-boot-mpidr`: el MPIDR de arranque es constante de placa
  (`A5XELTE_BOOT_MPIDR`: A5 `0x0`, herolte `0x100`).
- **Kernel completo hasta la espera del root** (run 39481021599, kernel
  sha256 `ffa3d8ea…432f`, misma cmdline). Foto del usuario: `A5XELTE CPU:
  cpu=0 mpidr=0x100 came alive; SGI1 OK`, `1/1 CPUs initialized, SGI1
  verified`, BSD init, AppleKeyStore, IOWatchdog, IOCoreSurfaceRoot, HID de
  botones/touch, SWEET AMFI (0201) y Sandbox registrados, HFS 627.100.6,
  self-tests de Skywalk `PASSED`, `lo0`/`gif0`/`stf0`, y finalmente
  `Waiting on <dict>IOProviderClass IOMedia, Content Apple_HFS</dict>`.
  Es el punto esperado: no hay driver de almacenamiento todavía.
- **Primer probe UFS** (`0204`, run 39484347438, kernel `d3905386…45f2`,
  `ufsprobe=1`): `cap 0x383ff0f ver 0x200 hcs 0x10f hce 0x1 is 0
  utrlba 0x0:ef002000 dbr 0 rsr 1`, `txprdt 0xc rxprdt 0xc nexus 0xffff`.
  El host quedó vivo tras S-Boot y tomó nuestra lista. TEST UNIT READY en
  LUN 0 (3 veces): `ocs 0x7 upiu 0x21 response 0x1 status 0x2`, o sea un
  UPIU de respuesta real con CHECK CONDITION: el transporte (UTRD con
  offsets en bytes, PRDT, NEXUS, doorbell) funciona. El probe no siguió a
  READ porque abortaba tras el TUR. Siguiente: imprimir el sense, probar
  LUN 0..7 y leer LBA1 aunque falle el TUR.
- **Segundo probe UFS** (run 39486812960, kernel `00f0b0da…deb1`): LUN 0–3
  responden NOT READY (sense key 2, ASC/ASCQ 0/0); LUN 4–7 ILLEGAL REQUEST
  ASC 0x25 (no existen: el S7 tiene 4 LU). READ(10) LBA1 en LUN 0: NOT
  READY. Hipótesis: S-Boot deja el dispositivo en un modo de bajo consumo;
  Linux lo reactiva con START STOP UNIT (ACTIVE) al W-LUN UFS Device
  (`0xD0`). `0204` ahora lo hace antes del primer comando (probe e init).
- **Tercer probe UFS: lectura funcionando** (run 39489906319, kernel
  `869c4c5f…d74a`). W-LUN `0xD0` TUR: NOT READY ASC/ASCQ 04/02
  ("initializing command required"); `START STOP UNIT (ACTIVE) 0`; LUN 0–3
  TEST UNIT READY 0; `READ(10) LBA1 0, signature EFI PART`; GPT de 128
  entradas de 128 bytes en LBA 2; particiones p1 `BOTA0` … p17 `USERDATA`
  (~21,5 GB, bloques de 4 KiB). Primera lectura del UFS desde XNU.
- **Primer root montado desde UFS.** Volumen HFSX de 32 MiB
  (`hfs-test-image`, sha256 `043f1459…8b94`) escrito por adb/TWRP al inicio
  de USERDATA (`/dev/block/sda18`); BOOT con `rd=ufsroot0 ufsroot=USERDATA
  cs_enforcement_disable=1` (mismo kernel `869c4c5f…`); ambos verificados por
  readback. Foto: `"USERDATA" on LUN 0: first block 0x22e0ac, 21566 MiB,
  read-only`, `BSD root: ufsroot0, major 1, minor 0`, `hfs: mounted HEROTEST
  on device b(1, 0)`, `root volume is not authenticated (error 25);
  continuing unsealed`, `devfs_kernel_mount: kernel_mount failed: 2` (la
  imagen no tiene `/dev`), y pánico esperado `exec of /sbin/launchd failed,
  errno 2`. Siguiente: imagen raíz de iOS 16.
- **Root de iOS 16.7.16 (iPhone X, D22AP) en USERDATA.** Workflow `ios-root`
  en el repo privado `wardevsa/ios-herolte-root` (la imagen es software de
  Apple; no se publica): HFSX de 20480 MiB, 3 partes gzip verificadas por
  SHA-256. Escrita con `tools/herolte-flash-root.py` (bloques de 64 MiB con
  readback SHA-256, ceros escritos en el teléfono; un corte del servidor adb
  se retomó con el archivo de estado): 320/320 bloques, imagen sha256
  `2e200c51…13ca8`, firma `HX` en el offset 1024. ADT con `/product` real de
  D22AP (63 propiedades) y kernel `d706ccd8…e271` (incluye 0205). Boot:
  `rd=ufsroot0 ufsroot=USERDATA ufsrw=1 rootrw=1 cs_enforcement_disable=1
  unentitled_ios_sim_launch=1 ignition_level=1 launchd_unsecure_cache=1
  wdt=-1 -wdt_no_pmu wdt_test=no_user_checkin`, verificado por readback.
- **Primer arranque de iOS** (log persistente 0206, kernel `012d056a…af10`,
  53 flushes): launchd hace todo el early boot (fsck, mount-phase-1/2,
  keybag, obliteration, launchd_cache_loader con `launchd_unsecure_cache`) y
  llega a `Early boot complete`; lanza SpringBoard, backboardd, keybagd,
  bluetoothd, fairplayd.H2, etc. SpringBoard aborta en loop (24 veces):
  `NSInternalInconsistencyException: We expect a valid bounds for
  configuration ... Main-External ... CADisplay.name = Wireless ... bounds
  {{0,0},{0,0}}` — no había display principal: el `disp0` del ADT decía
  `samsung,herolte-display` y AppleCLCD matchea `samsung,a5xelte-display`.
- **Con el ADT corregido** (boot `67953d9b…ea19`, mismo kernel): `SWEET FB:
  AppleCLCD 1440x2560 stride 5760 at 0xe2a00000 ... presented as 1125x2436`,
  backboardd configura el display (`display on`) y crea superficies
  1440x2560 y 1125x2436; **SpringBoard ya no crashea** (solo CommCenter, sin
  módem, y driverkitd). En ~5 min de log todavía no hay ningún `swap`.
- **Arranque largo (~20 min) con el ADT corregido:** log hasta el flush #37
  (46 KB). backboardd hace `SwapBegin` (sel 4) y sel 52, pero nunca
  `SwapEnd` (sel 5): ningún `SWEET FB: swap`, ninguna registración de
  notificaciones de vsync. El log deja de crecer bastante antes del final.
  `0207`: sampler de hilos (`sweet_sample.c`, SpringBoard/backboardd, a los
  90 s y cada 120 s) y latido `HEROLTE LOG: alive N s` cada 60 s.
- **Muestreos 0207** (kernel con sampler, ~14 min, latido estable cada
  60 s: el sistema no está colgado). Simbolizado contra la dyld cache de la
  imagen: el hilo `IOMFBServer` de backboardd rasteriza con el renderer de
  CPU de QuartzCore (`CA::OGL::SW::scanline`, `vAlpha_Blend` de vImage) y
  reintenta `eagl_init` (busca GPU) en cada `render_for_time`; el hilo
  principal de backboardd queda en `CA::Display::Display::update` (mach_msg)
  y SpringBoard espera en `FBSystemShellInitialize` (check-in síncrono con
  backboardd). Con un solo A53 el primer frame no termina.
- `0208`: SMP en los 4 A53 (MPIDR `0x100..0x103`) por PSCI `CPU_ON`, IPIs
  GICv2 dirigidas por la máscara de ITARGETSR0 de cada núcleo (adaptado de
  los pendientes 0112/0113 del A5). Requiere `cpus=4`.
- **Primer arranque con 4 núcleos** (`cpus=4`, boot `77af8df8…d298`):
  foto `A5XELTE CPU: cpu=1..3 PSCI CPU_ON rc=0 ... came alive; SGI1 OK`,
  `4/4 CPUs initialized, SGI1 verified`; el arranque va notablemente más
  rápido. Log (flush #67, 11 min): el hilo principal de backboardd ya no se
  bloquea; ahora espera en `DMPerformMigration` (XPC síncrono) mientras
  `com.apple.migrationpluginwrapper` aborta (3 veces), y SpringBoard sigue en
  `FBSystemShellInitialize`. CommCenter crashea 45 veces (sin módem). Sin
  `swap` todavía.
- `tools/herolte-tune-ios-root.sh` (en el workflow `ios-root`): como las
  imágenes v12/v13 del donor, `LastSystemVersion` en
  `com.apple.migration.plist`, CommCenter fuera de `launchd.plist`,
  `BKNoWatchdogs` + excepción de watchdog para Setup y el esqueleto
  `/private/var/containers`. `herolte-flash-root.py --diff` reescribe solo
  los bloques de 64 MiB que cambiaron.
- **Root ajustado** (22 bloques reescritos con `--diff`, imagen
  `6e77614c…c156`): sin migración ni CommCenter. **Primer SwapEnd de
  backboardd** (`sel 5`, registro de 1132 bytes), seguido de inmediato por
  `display off` (el driver hace el fundido a negro y no presenta), luego
  `display on`; SpringBoard crea sus primeras IOSurfaces (ids 7–10). Muestreo
  a los ~6 min: SpringBoard en `GSEventRunModal` (UI arrancada), backboardd
  rasterizando en 4 hilos (`CA::OGL::SW::image_sampler`). Siguiente BOOT
  (`a3bce0c3…0758`): `a5fb_keep_on=1 a5fb_noconsole=1 a5fb_perf=1`.
- **0209 (volcado de registros de swap):** los dos primeros swaps son
  frames negros a propósito (`0x104=0x80000007`, todos los ids de superficie
  0, fondo `0x10c=0xff000000`); después no llega ningún swap con contenido.
  backboardd crea sus superficies de render como `0x62336138` ('b3a8', 2
  planos) de 1440x2560 y 1125x2436: la superficie por defecto (panel
  1440x2560) contradice el tamaño presentado (1125x2436).
- **🍎 iOS en pantalla (2026-10-22, boot `a2d97ebe…2239`, `sweetfb_native=1`):**
  con el tamaño real del panel, primero el logo de Apple y después la
  pantalla de configuración "Hola" (bonjour), con hora, batería e indicador
  de inicio de iPhone X. Táctil y botones sin driver todavía.
- `0210`: botones por GPIO ALIVE (`0x10580000`, del DTB del BOOT): Power
  GPA2 pin 4; Vol+/Vol-/Home GPA0 pines 3/4/5, activos en bajo, solo lectura
  con antirrebote (driver del A5 parametrizado). Táctil: `sec_ts` en 0x48 de
  HSI2C `0x14E10000`, IRQ GPA1 pin 0 (pendiente).
- **Botones en el teléfono (boot `8c9c5843…dd25`, 0210):** los cuatro se
  detectan y llegan a iOS (`SWEET HID: key 0xe9/0xea/0x40/0x30`). Power
  bloquea/desbloquea (con `a5fb_keep_on` la imagen queda congelada y al
  despertar vuelve "Hola"); Home y volumen no cambian nada en "Hola"
  (identidad iPhone X: se pasa deslizando hacia arriba).
- `0211`: driver táctil `bsd/dev/herolte_touch.c` (sec_ts en 0x48 de
  HSI2C `0x14E10000`, pines GPF1-0/1 función 2, INT GPA1-0 por sondeo cada
  5 ms; eventos `0x71` de 8 bytes, coordenadas 0..4095 escaladas a
  1440x2560) y `SweetHID` con la geometría del panel del S7. No toca las
  LDO32/33 del PMIC: si no responde, lo deja anotado.
- **0211 en el teléfono:** GPF1 `dat=0` y GPA1 `dat=0` (SDA/SCL e INT en
  bajo), el HSI2C táctil queda en `trans=0x2000c` con el primer byte en la
  FIFO: el sec_ts está sin alimentación después de S-Boot.
- **0212 en el teléfono:** el batcher del PMIC (`0x10550000`) completa el
  envío del registro, pero la lectura queda en `bat_state=0x200` con la FIFO
  RX vacía; no se encendió nada (la verificación de voltaje no llegó a
  correr). `0213`: init del bus como el probe de Linux (reset, master, código
  HS `0x0f`, HS|AUTO), tres formas de lectura (ext de Linux, 7 bits, con STOP)
  y volcado de registros en cada falla.
- **0213/0214:** ambos congelaron el teléfono (0213 tras resetear el HSI2C
  del PMIC; 0214 al arrancar el primer programa del batcher a ~56 s).
- **0215 (sondeo de solo lectura, arrancó bien):** PMU APM
  `config=0x1 status=0x10000 option=0` (M3 alimentado pero retenido, sin
  `ENABLE_APM`), mailbox `0x11240000` todo en 0, SRAM `0x11200000` con una
  tabla de vectores Cortex-M válida (`00004000 0000009d …`): S-Boot deja el
  firmware del APM cargado y el M3 detenido.
- `0216`: alimentación del táctil por el APM, como Linux con la pantalla
  encendida: liberar el M3 (`APM_CONFIG |= 1`, IRQ del mailbox a 0,
  `APM_OPTION |= ENABLE_APM`) y pedirle por mailbox lecturas/escrituras del
  S2MPS16 (LDO32/33). El batcher queda tras `herotouch=2`.
- **🖐 Táctil funcionando (0216, boot `626b33c7…2d1d`):** el APM responde
  por mailbox (S2MPS16 `id=0x2`, `L32CTRL=0x2e`, `L33CTRL=0x3c`;
  escrituras `0xee`/`0xfc` con respuesta `0xa`, readback correcto); con las
  LDO encendidas SDA/SCL suben (`GPF1 dat=0x3`), el sec_ts está en modo app
  (`0x20`, id `ac a5 52`, tx=15 rx=26) y los toques llegan a iOS
  (coordenadas 0..4095 confirmadas). Muy lento y el gesto de deslizar hacia
  arriba no se completa: lecturas I2C con `int=0x400` (NACK) justo después
  de apoyar el dedo pierden los eventos de movimiento.
- `0217`: reintentos de lectura como `sec_ts_i2c_read()` (hasta 10),
  contadores `moves/i2c_retries/lost_reads`; las pausas de 11 s solo con
  `herotouchslow=1` (el táctil queda listo a los pocos segundos).
- **0217 en el teléfono:** `moves=835 i2c_retries=6 lost_reads=0`: los
  movimientos llegan completos; el gesto en "Hola" no avanza porque Setup
  espera CoreTelephony/activación (igual que el donor).
- **🏠 Pantalla de inicio de iOS (2026-10-23):** imagen con Setup marcado
  como completo (imagen `035edb65…d60a`, flasheo diferencial de 155
  bloques): pantalla de inicio y Centro de control con el táctil. Sin apps
  (el staging excluía `/Applications`; dos iconos "Waiting…") y muy lento.
- `STAGE_ALL_APPS=1` en `ios-root` (todas las apps, ~215 MiB) y `0218` +
  ADT `cpu4..7`: los 4 Mongoose (MPIDR `0x0..0x3`) como lógicos 4–7 con
  `cpus=8`.
- **8 núcleos (ADT con `arm,cortex-a53` también en los Mongoose):**
  `8/8 CPUs initialized`; `0219` confirma contador común a los dos clusters
  (lag < 1 ms) y temporizadores que despiertan en los 8 (21 ms sobre 20).
  Los Mongoose reportan `midr=0x531f0011`, `ctr=0x84448005` (línea de
  I-cache de 128 B frente a 64 B en los A53).
- Con todas las apps se quedaba en el logo: `lsd` no terminaba de sembrar la
  base de LaunchServices porque MobileGestalt calculaba el UDID y esperaba
  para siempre `mac-address-bluetooth0` (no estaba en `/chosen`). Con MACs
  sintéticas en el ADT (`02:48:45:52:4f:0x`): **pantalla de inicio con
  iconos** (Fotos, App Store, Ajustes, Teléfono, Safari, Mensajes) y
  Ajustes > Información abre ("iPhone X", iOS 16.7.16, 21 GB).
- **Batería (0220/0221):** el fuel gauge es el del MAX77854 (`0x36` en
  HSI2C_1 `0x13650000`, pines GPD1-2/3; en HSI2C_0 no hay ACK). Lecturas
  reales en el teléfono: 100 %, 4339 mV, +114 mA con cargador; 4043 mV,
  −749 mA sin él; FULLCAP ≈ 2000 mAh. iOS muestra 100 % → 99 %.
- **Botón de encendido (0220):** con `a5fb_keep_on` se acepta el apagado de
  pantalla si llega < 3 s después de pulsar Power; bloquea y apaga la
  pantalla, y vuelve con la pantalla de bloqueo.
- `0222`: `sweetfb_scale=1` experimental, iOS dibuja 960x1706 y el kernel
  escala x1.5 (menos píxeles para el renderizado por CPU).
- **Más RAM (2026-10-23):** el segundo banco de DRAM (`0x880000000`,
  2 GiB, sin `reserved-memory`) para XNU con `mkadt_herolte.py --bank2`.
  Con 2 GiB el kernel ve la memoria pero entra en pánico en
  `kmem_range_init` (no entran sus rangos virtuales). Con
  `--bank2-mb 1024` arranca; los secundarios no llegaban (CPU_ON rc=0 con
  entrada > 4 GiB) y `0223` entra por un trampolín en `0x8fffe000`:
  **1 GiB y 8/8 núcleos**, pantalla de inicio "bastante más fluida, abre
  todo mucho más rápido".
- **0224:** copia a pantalla en paralelo (3 hilos ayudantes): de 10–20 ms a
  ~5 ms por cuadro, hasta 16 fps con movimiento. El log de `kmem` mostró
  por qué 2 GiB no entraba: el kernel (configuración macOS) reserva un
  compresor de 16 × RAM; `vm_compression_limit` lo limita. Con 2 GiB pasa
  ese punto pero entra en pánico en `write_pte_fast` (PTE no alineada,
  páginas de 16 KiB sobre 4 KiB). **Configuración actual: `--bank2
  --bank2-mb 1536`, `vm_compression_limit=98304`, `cpus=8`: 1.5 GiB,
  arranca.**
- **GPU Mali-T880 (0225/0226):** el dominio G3D y los relojes ya vienen
  encendidos de S-Boot; `GPU_ID=0x08802000` (Mali-T880 r2p0), 12 shader
  cores (`0xff0f`), 1 tiler, 1 L2. Con `herogpu=3`: L2, shader core 0 y
  tiler encendidos (ready `0x1`) y **primer trabajo en la GPU**:
  `WRITE_VALUE` en JS1/AS0 con `irq=0x2 mmu=0 exception=1 output=0`, sin
  fallos y sin afectar a iOS.
- **🎨 La GPU dibuja (0227–0230, 2026-10-24):** el descriptor simple de la
  T720 (SFBD) da `DATA_INVALID_FAULT`; con el multi-target de Mesa v5
  (MFBD) y el tiler "desactivado con jerarquía" (máscara 4096, cabecera de
  512 bytes) el fragment job escribe **256/256 píxeles** en memoria
  privada, y con `herogpu=6` **pinta toda la pantalla 1440x2560 de verde
  en 16.6 ms con un solo shader core** (foto del usuario). La copia de iOS
  se pausa 8 s (`sweet_fb_hold_until`) para que se vea.
- **0231:** los **12 shader cores** (`0xff0f`) encienden con la tensión de
  S-Boot y pintan la pantalla entera en **3.26 ms** (5× más que un núcleo),
  estable. `COHERENCY_FEATURES=0`: la GPU no ve las cachés de la CPU, así
  que leer una superficie de iOS exige limpiarla antes (3.8 ms, un núcleo).
  La copia por "preload" del render target da `DATA_INVALID_FAULT`; Mesa
  no usa preload en Midgard (copia con un fragment shader). Copiar con la
  GPU frames dibujados por la CPU no compensa: la aceleración real pasa
  por shaders (primero un triángulo) y, a la larga, por traducir lo que
  pide CoreAnimation/Metal.
- **0232/0233: primer dibujo 3D, un triángulo con shader** (foto del
  usuario). Un tiler job (JS1) guarda el triángulo en la lista de
  polígonos (cabecera 32 palabras, cuerpo 48) y un fragment job (JS0)
  limpia la pantalla y ejecuta un shader Midgard de un bundle, ensamblado
  a mano (`tools/herolte-midgard-shader.py`). Todo en 16 ms. En 0232 no
  se veía nada porque el alpha test fijo de Midgard quedó en NEVER; con
  ALWAYS (0233) el triángulo aparece. Sale casi negro (`02020202`): el
  shader escribe r0 como fp32, y las constantes fp16 1.0 se leen como
  ~0.008. Siguiente: texturas → escalado por GPU (iOS a 720p).
- **0234: primera textura, escalado por GPU** (`herogpu=9`, foto del
  usuario). Una imagen de 180x320 se dibuja como un quad de pantalla
  completa con filtro bilineal: la GPU la agranda 8x a 1440x2560. Sin
  vertex shader, como el preload de Mesa: un varying con coordenadas de
  texel sin normalizar. Shader de 4 bundles ensamblado a mano (ld_vary,
  imov a r28, textura, writeout). Los píxeles leídos coinciden con sus
  texels, y en el borde de un cuadro sale la mezcla del filtro.
  **3.26 ms con los 12 cores** (34 ms con uno). Siguiente: que iOS
  dibuje a 720x1280 y la GPU escale cada frame a la pantalla.
- **0235: iOS en pantalla a través de la GPU** (`sweetfb_scale=1
  sweetfb_gpu=1`). Cada frame de iOS es la textura del quad de 0234:
  ~4.4 ms por frame con la limpieza de caché, sin fallos. Más fluido, pero
  el cuello de botella es CoreAnimation dibujando en la CPU (3-11 fps según
  la pantalla). 960x1706 son 320 puntos @3x, más angosto que cualquier
  iPhone de iOS 16: la interfaz se rompe. 1125x2001 (0236) tampoco sirve:
  UIKit elige la barra de estado por ancho en píxeles y notch.
- **0237:** como syncmodz/ios-s9, el ADT describe un iPhone XR entero
  (`--scale2`: 828x1792 @2x, subtype 1792). La GPU lo dibuja a alto
  completo con barras negras a los lados; el touch se normaliza sobre esa
  franja. Pendiente de probar.
- **0238 (de ios-s9):** los hilos de UI y render van a los Mongoose
  (cpus 4-7) en vez de los A53, y AppleKeyStore responde wrap/unwrap
  (securityd reintentaba sin fin y cada llamada iba al log). Probado:
  más fluido, log de AKS de 1600 a 19 líneas. El XR deja barras negras y
  el Centro de Control sin blur (fondo negro: el blur es de Metal).
- **0239: HeroGPU, etapa 1 de la aceleración completa.** Servicio IOKit
  para que procesos de iOS usen la Mali (GetParam con los números de
  Panfrost, CreateBO/FreeBO/MapBO, Submit). Selftest en el teléfono:
  `GPU_ID 0x880 rev 0x2000 shaders 0xff0f`, un WRITE_VALUE desde un buffer
  de usuario en VA 0x40000000 → **OK en 115 µs**. Siguiente: Mesa Panfrost
  compilado para iOS con un libdrm sobre HeroGPU (como Bergamota con
  freedreno), luego la capa Metal de Chlorophyll.
- **0240-0242: programas de iOS en la GPU.** Zona de "drop" en USERDATA
  (`tools/herolte-drop.py` desde TWRP, el kernel la instala en
  `/private/var/herolte/` cuando la raíz pasa a lectura-escritura; launchd
  corre `autorun`). 0242 corrige `pmap_sync_page_attributes_phys`, que
  truncaba direcciones físicas sobre 4 GiB (panic en MapBO). Probado con
  `herogpu-test` desde iOS: los parámetros de Panfrost, WRITE_VALUE → OK en
  358 µs y un FRAGMENT clear de 64x64 → **4096/4096 píxeles OK en 197 µs**.
- **Etapa 2 (`gpu/mesa`, workflow `mesa-ios`):** Mesa 25.0.7 Panfrost
  (Gallium + compilador Midgard) dentro de OSMesa, compilado para iOS, con
  un libdrm que traduce los ioctl de Panfrost a HeroGPU. `osmesa-test`
  dibuja un triángulo con OpenGL y mide fps; resultado en el log del kernel.
- **Primer OpenGL en la Mali desde iOS.** `GL_RENDERER = Mali-T880
  (Panfrost)`, GL 2.1. Hicieron falta dos arreglos: 0243 configura la GPU
  como Linux para un T880 r2p0 (`SHADER_CONFIG.LS_ALLOW_ATTR_TYPES`,
  clock gate del tiler, throttle del JM), y el libdrm devuelve a Mesa el
  tamaño real del heap del tiler (32 MiB, no los 128 pedidos: el tiler
  escribía sobre otros buffers → DATA_INVALID_FAULT 0x58). Resultado: sin
  fallos, centro rojo `0xff0000ff`, fondo azul, 8192 píxeles del triángulo
  exactos; **256x256 a 159 fps** con `glFinish` en cada frame. Siguiente:
  la capa Metal de Chlorophyll sobre este Panfrost, para CoreAnimation.
- `sweetfb_scale=1` (0222) muestra la imagen rayada y duplicada (las
  superficies a 960x1706 tienen otro formato): queda desactivado.
- Pendiente: nodo `/product` del ADT a partir del IPSW; root (UFS).

## 2026-10-31: aceleración por GPU usable

- Resolución interna de iPhone 8 (750x1334 @2x, `mkadt_herolte.py --iphone8`), escalada por la GPU al panel. La fluidez mejora mucho.
- Boot args: `sweetfb_native=1 sweetfb_scale=1 sweetfb_lw=750 sweetfb_lh=1334 sweetfb_gpu=1 herogpu_mhz=650 herocpu_mhz=2600 herosb=1`.
- Medido: Mongoose 2598 MHz a 1075 mV, GPU 650 MHz. En reposo 7-22 % de 800 % de CPU.
- `hero-run` mueve `BTAudioHALPlugin` fuera de `HAL/`: `launchd` y `mediaserverd` dejan de gastar CPU. La pista es de ios-s9.
- Fondo: imagen fija desde SpringBoard (`herosb.c`, `herosb=1`). No hay proveedores de PosterBoard, la galería sigue vacía.
- Lista de servicios desactivados: `tools/herolte-disabled.list`, copiada como `disabled.list` a la zona de drop. Con 41 servicios SpringBoard no dibujaba: algún servicio de los otros 13 es necesario, sin identificar.
- Gestos: con `home-button-type` 2 aparece la barra roja. Con 1 no hay barra, pero tampoco gestos. Forzar `_UIStatusBarVisualProvider_Phone` en SpringBoard lo hace cerrarse; `gestures.off` en la zona de drop deja esos ganchos apagados.
- `JOB_READ_FAULT` (0x42): tras él ni un trabajo en memoria del kernel corre; no lo curan hard reset ni apagar el dominio G3D. No se vio desde el cambio de resolución, en pocas pruebas. Causa desconocida.
- Falta: límite térmico, audio, Wi-Fi.
## Pantalla a 60 Hz reales (0296-0297)

El bootloader deja el vclk de DECON_F en el oscilador de 26 MHz (`MUX_DISP_PLL`, CMU_DISP0 +0x200, bit 12 en 0): 363 ciclos por línea, 35,8 ms por cuadro, un TE de cada tres, 20 Hz, aunque iOS dibujara 40-50 fps. Con el vclk en DISP_PLL (62,5 MHz): 14,88 ms por cuadro, período 16,74 ms (59,7 Hz), medido con el contador de líneas (DECON +0x8c). Sin relación: eclk, relojes de bus, MULTI_PKT_CNT. Los cortes horizontales siguen: un solo cuadro en memoria, reescrito mientras DECON lo lee.

## Sonido en iOS (0300-0303)

El I2S está en reset hasta `CON_RSTCLR` (+0x00 bit 31); sin eso una escritura traba un núcleo. MOD: OPCLK de PCLK, CDCLK de entrada, esclavo. `heroaudio=3`: `/dev/hakios-audio` antes de que arranque mediaserverd y el plug-in AudioServerPlugIn de HakiOS (`gpu/hakios-audio`, MIT) en `/System/Library/Audio/Plug-Ins/HAL/HakiosAudio.driver`. El kernel alimenta el FIFO a mano, por tiempo. Probado: tono de llamada y teclado por el parlante, barra de volumen.

- **Extensiones, GPU y Wi-Fi (2026-11-01):** el kernel ahora responde la consulta `0x60` de AMFI (idea del kernel del JM21): iOS pasa de 1 a 516 plug-ins y aparecen widgets y fondos. El cuelgue que siguió era un bug propio: la tabla L3 número 176 del pool de usuario caía sobre el nivel 0 de la GPU (`0x8ffc0000`), a unos 350 MB de buffers, y ningún reset lo arreglaba; `0307` le da al pool su bloque en `0x8fc00000`. Wi-Fi: con el orden y los tiempos de Samsung el enlace PCIe sube al primer intento, `14e4:4415`, ChipCommon `0x17094359`. Falta firmware y driver. Pendiente: `CalendarWidgetExtension` usa 2 núcleos unos 7 minutos tras cada arranque y launchd reintenta `AegirPoster`.
- **Wi-Fi escanea (0308-0311, 2026-11-02):** `bsd/dev/herolte_wifi.c` carga el firmware del teléfono (de VENDOR, en la zona de drop, fuera del repositorio) en la TCM como brcmfmac y lo arranca: RTE 9.96.17 en BCM43596 C0. Colas msgbuf en RAM del host (`0x8f000000`, 1 MB), ioctls por la cola de control: `cur_etheraddr`, `ver`, CLM, `WLC_UP`, `event_msgs` y `escan`; el primer escaneo vio 11 redes en 2,4 y 5 GHz. `0310` agranda el io_map a 64 MB. Falta: asociarse con WPA2, el camino de datos y la interfaz para iOS.
- **WPA2 (0312-0313):** con `sup_wpa=1` el firmware responde -23 (BCME_UNSUPPORTED): el de Samsung no trae supplicant (Android usa wpa_supplicant). En 0312 se asocia y el enlace sube, pero el AP lo echa cada ~5 s con razón 15 (timeout del 4-way handshake), 33 s sin claves. `0313` hace el handshake en el kernel como wpa_supplicant: buffers en el anillo rx, un flow ring hacia el AP, nuestro elemento RSN por `wpaie`, PMK por PBKDF2, PTK, MIC, desenvuelto AES de la GTK y claves por `wsec_key`; después un DHCP DISCOVER a broadcast para probar las dos claves. SHA-1/HMAC/PBKDF2/AES escritos en el archivo (el kernel solo trae SHA-256), verificados en una transcripción a Python contra hashlib e IEEE/RFC 3394, y de nuevo en el teléfono al arrancar.
- **📶 Wi-Fi conectado con WPA2 (0313, run 41519331439, kernel `8c2f42a5…acaf`, log `wifi-0313`):** `crypto check: PBKDF2 ok, AES key unwrap ok`, PMK en 18 ms, `wpaie 0`, flow ring 2 abierto, handshake 1/4→2/4 y 3/4→4/4 (GTK índice 1, 16 bytes), `keys: pairwise 0, group 0`, **`CONNECTED with WPA2 in 1649 ms`** (-46 dBm) y **`DHCP OFFER: 192.168.1.25 from 192.168.1.1`** enviada a broadcast: las dos claves funcionan; 3 de 3 frames enviados. Las BOOT de prueba de Wi-Fi (0310-0313) usaban una línea sin `heroaudio=3` (por eso no había sonido); BOOT diaria `xnu-boot-0313-daily` = línea diaria + `herowifi=1`, sin `herotwrp`. Falta: drenar los anillos siempre (hilo), `en0` y Apple80211 para iOS.
- `0314` (en0 para iOS): las capas de apollo (xnu 0128-0135, de HackiOS, APSL 2.0) para el mismo xnu-8796 e iOS 16.7.16: `sweet_net.c` (en0 con la KPI de interfaces), `sweet_sta.c`, `sweet_apple80211.c` (las peticiones de wifid), `SweetWLAN.cpp` e `IONetworkStack` (`SweetNetworkStack.cpp`, con el sustituto del demonio de IOKit; `herowifiquiet=0` lo quita). `herolte_wifi.c` es el enlace y la estación debajo: hilo de servicio (1-5 ms), escaneos y uniones pedidos por wifid, salida de en0 por una cola, la dirección del ADT (`mac-address-wifi0`) puesta en el firmware con `cur_etheraddr`, `network.txt` como red fija. en0 se crea en `bsdinit_task` antes de launchd.
- **🌐 Internet por Wi-Fi en iOS (0314, run 41525337235, kernel `1bb58e29…4649`, log `wifi-0314`):** en0 hecho antes de launchd, `SweetNetworkStack: opened by configd; busy state 0`, la estación conecta sola a la red fija (1727 ms) y `en0's link (the BCM4359) is up`; configd lee SSID/BSSID/AUTH_TYPE; **`en0 so far 9391 frames sent, 11076 received (15154960 bytes)`**. Safari intenta cargar apple.com (parpadea blanco/negro: dibujo, no red). Sin ícono de Wi-Fi: **wifid no se lanza nunca** (ninguna petición de wifid): su job tiene `_LimitLoadToDeviceTree = ("wlan", "marconi-wifi")` y el ADT no tenía `wlan` (apollo, boot 53). `mkadt_herolte.py` agrega `/arm-io/wlan`; BOOT `xnu-boot-0314-wlan` = la diaria con ese nodo, sin probar todavía.
- **Con wlan (log `wifi-0314w`):** wifid arranca y habla (CARD_CAPABILITIES, POWER, RSSI_BOUNDS, escaneos; ícono de Wi-Fi). Safari parpadea: WebContent se lanza 56 veces y muere con `sig 11, pc 0x0`, `lr` fuera de la dyld cache; simbolizado: `WebCore::Document::resolveStyle` → código del JIT de selectores CSS que salta a 0. Calor: `CalendarWidgetExtension` al 200 % varios minutos y `xpcproxy` relanzando WebContent; el kernel en reposo 5-6 %. La línea de arranque diaria + `herowifi=1` pasaba los 607 caracteres y cortaba `sweetsample=-`.
- `0315`: `mmap(MAP_JIT)` rechazado (`herojit=1` lo permite), como para una app sin dynamic-codesigning; Wi-Fi encendido por defecto (`herowifi=0` lo apaga) y en cuanto está `wifi/fw.bin` (antes 45 s fijos); `CalendarWidgetExtension` no arranca (como `AegirPoster`); `WLC_SET_PM` 2 al conectar; el hilo del chip duerme 20 ms en reposo. BOOT: la línea diaria sin `herowifi=1`.
- **0315 en el teléfono (log `boot-0315`):** Wi-Fi a 1 s de tener los archivos, conecta en 1,6 s. `HEROLTE JIT: com.apple.WebKit asks for JIT memory: refused`: WebContent ya no cae en loop (5 lanzamientos, no 56) y llega a dibujar, pero la página se ve **negra**; 2 de 5 mueren con `sig 5` en `_WebContentServiceInitializer` → JavaScriptCore. Rechazar `CalendarWidgetExtension` fue peor: SpringBoard, widgets de Mapas y Game Center al 150-390 % pidiéndolo (todo 800-1300 %). `0316` lo deja arrancar de nuevo.
- **Negro de Safari y fondos que faltan: caché de la CPU.** En `hakios-gl` (eagl.c) una imagen "compartida" (la textura es la memoria del IOSurface) que otro proceso dibuja con la CPU nunca se sincronizaba: `my_glBindTexture` y el bucle de inicio de cuadro saltan las compartidas ("una GPU que tiene la memoria muestra lo que hay"), y la Mali no es coherente (`COHERENCY_FEATURES=0`): lee la RAM vieja. Cada cuadro decía `0 textures refilled`. Ahora `shared_picture_fresh()` limpia la caché del IOSurface (SyncBO de HeroGPU) cuando su seed cambia y cada 30 cuadros. Sin probar.
- **0316 + hakios-gl con limpieza de caché (log `boot-0316`):** las limpiezas ocurren (20 anotadas), pero sigue igual: el fondo original de iOS 16 negro (algunos fondos sí andan) y Safari negro. Los fondos de iOS llegan como **ASTC 4x4** (`0x93b0`, 750x1334, 1004672 bytes): la T880 los acepta sin error y salen negros. `herodrm` ahora oculta a Panfrost los bits ASTC de `TEXTURE_FEATURES0` (20-23; `HERO_ASTC=1` los deja) y Mesa los decodifica por CPU al subirlos. Safari: el registro de creaciones de IOSurface se corta en las primeras 64 del arranque y los selectores se anotan una vez para todos, así que no se sabe qué pide WebKit; `0317` anota aparte las primeras 160 llamadas de WebKit/Safari con su respuesta. Además: `SWEET Sandbox: com.apple.WebKit.Ne privilege 10001 denied`.
- **0317 (log `boot-0317`):** `texture features 0xfffe003f: ASTC hidden` (pero en ese arranque no hubo subidas ASTC). Las llamadas de WebKit a IOSurface: crea superficies sin error (sel 0), puertos (35), sel 20/44/9; el proceso GPU de WebKit dibuja las páginas en superficies de 10 bits **`'w30r'` (750x1024) y `'b3a8'`**, y backboardd nunca hace textura de ningún formato de 10 bits "mostrado" (solo BGRA/RGBA de 8 bits): CoreAnimation sobre nuestro OpenGL ES no los muestra → negro. Causa: `/product artwork-display-gamut = "P3"` (iPhone X). `mkadt_herolte.py` pone `"sRGB"`; BOOT `xnu-boot-0317-srgb` = 0317 con ese ADT, sin probar.
- **Con el ADT sRGB (logs `boot-0317s`, `boot-0317s2`):** PosterBoard pasa a superficies `'BGRA'` (antes `'b3a8'`), pero el proceso GPU de WebKit sigue con `'b3a8'` (23) y `'w30r'` (5); Safari y el fondo original siguen negros. Desensamblado `WebCore::screenSupportsExtendedColor`: usa lo que le pasa el proceso de interfaz y si no, `MGGetBoolAnswer` con la clave ofuscada `Aixt/MEN2O2B7f+8m4TxUA`: la respuesta P3 sigue en la caché de MobileGestalt. `hero-run` borra una vez `SystemGroup/*/Library/Caches/com.apple.MobileGestalt.plist` (`mgcache.gone`); vale desde el arranque siguiente.

## 2026-11-07 — wifi y sonido en el S7 de prueba

- BOOT de control de 8 Plus, kernel del run 42300961206: firmware Samsung BCM43596 C0 9.96.16 y NVRAM cargados desde el drop. Sin CLM externo, la primera exploración del driver termina bien y encuentra tres AP. `wifid` habla con `en0`; al principio no hay canales, después del evento de encendido sí se contestan. No se registró una petición de exploración de `wifid` ni asociación; el usuario vio la lista vacía en Ajustes. Falta medir la petición con el interruptor tras inicializar el firmware.
- El mismo BOOT no activa `heroaudio=3`. La prueba usa el mismo kernel/ADT y agrega ese argumento y el plug-in HakiosAudio; el instalador de prueba compara los archivos instalados y deja intactos los ajustes gráficos. El audio en iOS requiere otro arranque si el HAL ya arrancó antes de la instalación.
- Prueba con `heroaudio=3 herotwrp=150`: el usuario informó «panic in bootloader» y volvió a TWRP manualmente. El log persistente recuperado coincide byte a byte con el BOOT anterior; no hay marcadores nuevos del driver o del instalador. El BOOT de prueba solo difiere del control en esos argumentos y el hash del encabezado. Se restauraron y verificaron el BOOT de control y el drop gráfico/wifi anterior; se reinició al sistema. No se ejecutó una segunda prueba de audio. Próximo diagnóstico: separar la habilitación del driver del despliegue del HAL y recuperar el texto exacto si vuelve a fallar.
- Wi-Fi confirmado por el usuario con el BOOT de control. Log posterior: siete escaneos correctos, seis eventos de fin de escaneo, un evento de fin de asociación, enlace `en0` activo y tráfico en ambos sentidos. La prueba de audio siguiente solo prepara HakiosAudio y su instalador en el drop, cuyo retorno se verificó; se conserva exactamente el BOOT de control, sin `heroaudio=3`. Pendiente comprobar los marcadores de instalación en el log de este arranque.
- El arranque de control instaló y verificó HakiosAudio, Info.plist y CodeResources. El instalador salió con código 0 y el contador de ciclos de la GPU dio 260 MHz. Se escribió y verificó un BOOT que solo agrega `heroaudio=3` al control, sin temporizador de TWRP. Pendiente el resultado en pantalla y el log de esa prueba.
- El usuario oyó el tono durante el logo de arranque y confirmó que el sonido funciona en iOS, aunque el volumen es bajo y la reproducción no es del todo correcta. Pendiente el log del arranque con audio para comprobar la apertura del dispositivo por el HAL y los contadores del FIFO durante la reproducción.
- El log de esa prueba confirma apertura por `mediaserverd`, volumen HAL 1.0 y hasta 19 suministros cortos del FIFO, con cero pérdidas de la cola. El usuario informó que YouTube no reproduce vídeo. Hubo tráfico en `en0` y peticiones de memoria JIT rechazadas por WebKit, sin diagnóstico de decodificación en ese log. Se instaló un BOOT de prueba con 1976 MHz Mongoose y 546 MHz Mali, y un complemento de SpringBoard para iconos 8% mayores y para ocultar únicamente la barra de diagnóstico si se identifica. Ambos paquetes se verificaron por lectura. Pendiente comprobar las frecuencias y los cambios visuales en el dispositivo.
- El log del BOOT de control confirma 8/8 núcleos, Mongoose a 1976 MHz en el PLL y Mali a 546 MHz mediante contador de ciclos. SpringBoard aplicó 56.00 → 60.48 pt. En la primera prueba automatizada (CI 42327839616), XNU entregó un evento Home a un cliente HID, produjo una captura de 480 × 853 y llegó al reinicio programado. La captura confirma que la barra roja seguía en el inicio después de que el escáner de SpringBoard agotara sus intentos. La espera de ADB y el escáner se ampliaron para la siguiente prueba. El procedimiento está en `docs/herolte-ui-test-handoff.md`.
- La segunda prueba automatizada completó el regreso a TWRP, recuperó una captura de 480 × 853 y restauró el BOOT de control con hash verificado. En la imagen se sigue viendo la barra roja. El control llegó a 59.3 fps en un intervalo activo y tuvo una mediana de 4.37 ms de copia por cuadro. Falta una secuencia de desplazamiento repetible para comparar fluidez.
- CI 42355796750, doce deslizamientos entregados en cada arranque y tres intervalos completos por prueba. Relojes del cargador: 13.1 fps y mediana de copia 5.67 ms. Mongoose 1976 y Mali 546 MHz: 20.7 fps y mediana de copia 4.39 ms. Ambas capturas muestran inicio, fondo y barra roja. La prueba incluye pausas fijas. Se restauró y verificó el BOOT de control tras ambas rondas.
- Mismo kernel y deslizamientos con EAGL/Panfrost a 1976/546 MHz. Puente normal: 28.6 fps, 9 de 441 swaps sobrescritos y copia mediana 4.51 ms. Puente HakiOS: 26.6 fps, 8 de 410 y 4.32 ms. backboardd envió trabajos a la GPU en ambos. Capturas con iconos, fondo y dock translúcido, pero la barra roja sigue presente. Se restauró y verificó el BOOT de control y se repuso el paquete anterior después de HakiOS. Próxima comparación: envío asíncrono de trabajos con el puente normal.
- Con `HERO_ASYNC=1` y el mismo BOOT de prueba se confirmaron envíos en cola: 30.3 fps frente a 28.6, 18/476 swaps sobrescritos y copia mediana de 4.67 ms. La captura conserva el fondo y los iconos. La barra roja y las bandas de Weather siguen visibles. Se restauró el BOOT de control y se verificó un drop con `HERO_ASYNC=0`.
- Perfil de backboardd durante la prueba con cola: 1490 muestras, 45.1% en `mach_msg2_trap`, 17.7% en QuartzCore y 12.8% en libOSMesa. No identifica un único cuello de botella. A 750×1334 con EAGL y cola: 36.9 fps y copia mediana de 2.82 ms. Captura con barra roja, iconos solapados y dock recortado, compatible con una escala 3× retenida a pesar del ADT 2×. No se adoptó ese modo. BOOT y drop de control verificados tras las dos pruebas.
- La sonda de SpringBoard confirmó UIScreen 414×736 pt a 3× con 1242×2208 y ~250×445 pt a 3× con 750×1334. MobileGestalt devolvió ArtworkDeviceSubType 2436 en ambos modos. Las dos pruebas terminaron en TWRP y se restauró el BOOT de control. El caché persistente es el siguiente candidato a aislar con copia de seguridad.
- Tras apartar y verificar el caché original de MobileGestalt, dos arranques 750×1334 dieron 375×667 pt a 2× y subtipo 1334. Las capturas muestran la barra normal, iconos sin solapar, fondo y dock completo. Las pruebas de deslizamiento marcaron 27.5 y 29.6 fps con pausas. La copia original de 8017 bytes, el BOOT y el drop de control se restauraron y verificaron. Falta validar fondo de bloqueo y optimizar el modo 2× con la interfaz correcta.
- El arranque de bloqueo a 750×1334, sin Home sintético, muestra el degradado a pantalla completa, los indicadores superiores y la indicación de pulsar Home. No se ven la fecha ni la hora grande. SpringBoard se había reiniciado antes de la captura. El arranque siguiente verificó los 8017 bytes originales del caché y se verificó por lectura el BOOT de control en TWRP. Se restauró y verificó el drop de control (paquete 1794081238). La comparación con el doble buffer IDMA y la temporización de CoreAnimation de upstream está anotada en `docs/herolte-ui-test-handoff.md`.
- CI 42410622025, prueba IDMA con 750×1334 a 2× y 2 GiB. La repetición en orden inverso tuvo doce deslizamientos por modo y ninguna entrada extra durante la ventana medida. Un buffer dio 28.6 fps con pausas y 46/477 swaps sobrescritos. Dos buffers dieron 31.4 fps y 0/473, con tiempo mediano de presentación de 5.69 ms frente a 2.65 ms. Las capturas muestran la misma página de inicio y el usuario confirmó que le gustó la interfaz con doble buffer. Se verificaron el caché original, el BOOT de control y el paquete 1794085251. El teléfono quedó en TWRP.
- CI 42414795440, temporización con doble buffer. Se repitieron los arranques que tenían entrada ajena a la prueba. Durante el arrastre, 29.3 solicitudes de flip confirmadas por segundo con la temporización original, 26.4 sin coalescing y 25.4 con el aviso de 120 Hz. Con las pausas, 31.7, 33.0 y 32.8 fps respectivamente. Se verificó el caché original y el BOOT de control antes de escribir el BOOT de uso normal con la interfaz aprobada de 750×1334, sin los argumentos del ensayo. BOOT y paquete 1794088300 verificados por lectura. ADB solicitó el reinicio normal.
- CI 42421869631, bloqueo y reactivación con la interfaz 750p. El camino de un paso escribió negro en 37.462 ms desde la petición de apagar la pantalla. La variante gradual no registró el final antes de reactivar. Ambas capturas muestran el fondo de bloqueo al despertar, sin reloj grande ni fecha. Se verificó y arrancó el BOOT diario con `herofade=0`, sin automatización de prueba. Se conserva el BOOT diario anterior para recuperar.
- En la prueba limpia de brillo, el gesto abrió Control Center y ambos arrastres llegaron a HID. La posición quedó en el centro y no hubo nuevas llamadas de brillo a IOMFB. El observador de SpringBoard registró `_canAdjustBrightness` falso en tres consultas. TWRP identifica S6E3HA3 `004044`. La lectura DCS produjo tres bytes, pero el analizador rechazó la respuesta. Se compiló localmente una corrección del analizador. Falta probarla en el teléfono.
- La prueba de video desde memoria reproduce SIGABRT de mediaserverd con la propiedad de alineación escalar. El diccionario permite avanzar a una IOSurface 420v 320×180 y luego ocurre SIGBUS en H264SW. No se verificó reproducción. La sonda de sensores solo leyó registros GPIO y de reloj. El BOOT de uso normal fue restaurado y verificado después de esas pruebas.
- La rama de RAM arrancó con 2048 MiB y volvió a TWRP. El proceso de prueba de 96 MiB fue terminado. En el siguiente arranque con el mismo BOOT de 2048 MiB y sonda de 16 MiB, no hubo retorno automático a TWRP y USB dejó de mostrar el S7. No se escribieron los BOOT de 2240 ni 3058 MiB. Se espera recuperación manual para restaurar el BOOT anterior.
- El usuario devolvió el teléfono a TWRP tras el pánico de la prueba de 2048 MiB. Se restauró y verificó dos veces el BOOT de bloqueo rápido y el paquete 1794141278.
- **3058 MiB en el teléfono (2026-11-08, kernel de CI 42441884465, BOOT `d9724ef6…`, `herotwrp=120`):** `HERORAM: hw.memsize 3206545408 bytes (3058 MiB)`, doble buffer activo (`HEROCAP: scanout 0x91000000, 1933 flips`), regreso automático a TWRP y BOOT diario `3f9c0da1…` restaurado y verificado; paquete de control 1794146305. Memoria: `free 141 active 1322 inactive 662` a los 60 s, `free 28 active 1372 inactive 988` a los 120 s. El usuario vio volver la pantalla de bloqueo: backboardd murió con SIGBUS (`sig 10`, `far` en el inicio de una página de una región malloc RW, tag 3) en `libobjc.A.dylib+0x3a9c` desde CoreFoundation/libxpc, y SpringBoard y los widgets cayeron con él. El mismo pc sin slide (`0x1800bba9c`) aparece en cuatro logs anteriores con 2 GiB (`idma-ab/trial`, `idma-ab/repeat`): el fallo es previo y no lo causan los bancos nuevos. Log en `s7-setup/night-tests/ram-3058-small`.
- BOOT diario de 3058 MiB `054157f5…` (kernel de CI 42441884465, ADT `herolte-750-3058m.adt`, la línea diaria sin `herotwrp`/`herocap`/`herohome`), verificado por lectura; el BOOT de 2 GiB `3f9c0da1…` queda para volver atrás.
- **Causa del SIGBUS de backboardd (kernel local con `0333`, que agrega ESR y atributos de la página al informe):** `esr 0x92000035 ec 0x24 fsc 0x35 … pa 0xe7104000 managed 1 wimg 0x6`. FSC 0x35 es "unsupported exclusive or atomic access": un LDXR/STXR de libobjc (sin LSE en los A53) sobre una página `VM_WIMG_WCOMB`. `SweetSurface::kernelAddress()` mapeaba con `kIOMapWriteCombineCache` también las superficies sobre memoria del cliente (0259, `IOSurfaceAddress`); `mach_make_memory_entry` aplica entonces `vm_object_change_wimg_mode` a todo el objeto malloc del cliente. `0334` mapea con el modo de la superficie (`mapCache`) y anota cuando un objeto anónimo pasa a no cacheable (`HEROLTE WIMG:`; quedan avisos de objetos de 4-6 páginas de backboardd, compatibles con los BO de HeroGPU).
- Kernel local (WSL, árbol de CI 42477676441) con 0326-0330, 0333, 0334 y de upstream 0321 (hilos de UI a Mongoose libres), 0324 (tope de CPU de widgets), 0325, 0330/0331 (límite térmico por TMU; los dos trozos de `SweetFramebuffer.cpp` adaptados a mano): 0 instrucciones LSE. Doce deslizamientos por arranque a 3058 MiB: control 32.9 fps (copia 5.30 ms), nuevo 34.0 fps (5.07 ms), nuevo con 2288/650 MHz 32.0 fps (6.09 ms, SoC 55 C frente a 45 C): no se suben los relojes. Sin SIGBUS de backboardd en los tres; los dos arranques de 3058 MiB anteriores con el kernel viejo lo tuvieron. TMU: `SoC 45 C (big 45, little 44, GPU 44, ISP 44)`. Logs en `s7-setup/perf-work`.
- Dos arranques de 300 s con el kernel nuevo (`soak-new-run1/2`): cero `sig 10/11`. En los cinco arranques con 0334 no volvió el SIGBUS de backboardd. Quedan abortos de MusicCoreSpotlightExtension y assetsd y terminaciones por jetsam.
- Kernel `perf3` (perf + 0332 + `0335`, que acepta el informe Ack/Error, tipo 0x02, después de la respuesta DCS), 0 instrucciones LSE, `cf0f72ac…`. Prueba con `heropanelid=1`: `HEROLTE PANEL: DCS 0x4 reply with error report 0x8004 (ignored)` y `HEROLTE PANEL: DCS ID 004044`, el mismo panel S6E3HA3 que TWRP. La lectura del panel durante el arranque hace caer el doble buffer: `HEROLTE FB2: one buffer from now on: flip not taken in 40 ms (after 47 flips)` (en perf2, después de 53). Por eso la copia de 2.5 ms de esas pruebas no es una mejora. `heropanelid` queda fuera del BOOT diario hasta que la lectura se haga antes de activar el doble buffer. Esa prueba tuvo un `sig 11` nuevo de `vmd` (`esr 0x92000006`, fallo de traducción sin página), que no apareció en los siete arranques anteriores: se vigila.
- **BOOT diario `c5d3b939…`** (kernel perf3, ADT `herolte-750-3058m.adt`, la misma línea diaria, sin `heropanelid` ni argumentos de prueba), verificado por lectura. Las lecturas DCS solo se ejecutan con `heropanelid=1`, así que este BOOT se comporta como el kernel perf probado. Para volver atrás: `054157f5…` (3058 MiB, kernel CI) y `3f9c0da1…` (2 GiB).
- El BOOT diario `c5d3b939…` funcionó 97 minutos sin SIGBUS. SoC a 41-42 C, más de 1.1 GB libres en reposo, doble buffer activo. Al usar el teléfono, mediaserverd tuvo cuatro SIGABRT seguidos (camino de la propiedad de alineación escalar). Quedan los abortos de MusicCoreSpotlightExtension (6) y assetsd (5). Log en `s7-setup/perf-work/daily-perf3-boot1`.
- Prueba de video con perf3 y `herovideoalign=1` (drop temporal con el reproductor y el clip, autorizado por el usuario; luego se restauró byte a byte y se verificó el paquete de control 1794146305 y el BOOT diario). AVFoundation pidió los 159809 bytes y mediaserverd creó la IOSurface 420v 320×180 (2 planos, 98304 bytes). Luego `triggered unnest … of DYLD shared region` y SIGBUS: `esr 0x92000047 fsc 0x7 wnr 1`, una escritura en `far 0x203afc040`, región `prot 1/3 tag 35`. Con el slide del caché 0x29578000 cae en `.27.dylddata` (datos de solo lectura del caché compartido). En la prueba anterior cayó en texto RX. Toda la pila está en un hilo de H264SW (`+0x13914`, `+0xec398`, `+0x115efc`, `+0x11c754`, `+0x118234`, luego `libsystem_pthread`). Es un puntero inválido del decodificador, no la dirección de la superficie. Para seguir hace falta el subcaché `.31` (H264SW en `0x1f0f39000`), que no está en el PC. No se mostró ningún cuadro y `herovideoalign` sigue fuera del BOOT diario.
- **Causa del SIGBUS de H264SW:** el caché compartido completo se sacó de la imagen raíz local (`s7-setup/ios-root-16.7.16-42281847558`, iNodes de `[HFS+ Private Data]`, fuera de git) y se desensambló con Capstone. `H264SW+0x13914` es la copia del cuadro decodificado al buffer 420v de salida. Kernel `perf4` con `0336` (registros y mapeo de cada puntero en el informe de crash, dirección de las superficies planares): la superficie 8 quedó en `0x108334000`, plano 0 en +64 (`x7 0x108334040`, correcto), pero el paso de fila destino era 0. Con `2*0 - 320` en 32 bits el puntero avanza 0xfffffec0 + 320 = 4 GiB por fila (`x10 0x208334040`) y cae en el caché compartido. `IOSurfaceClientGetBytesPerRowOfPlane` (iOS 16.7) lee el paso en `cliente + 0xe0 + i*0x80`, es decir +0x10 del registro del plano. `SweetSurface` solo escribía +0x08. El resto de los campos (ancho, alto, offset, tamaño, bpe, ew, eh, base) coincide. `0337` escribe el paso también en +0x10. Drop de prueba restaurado y verificado, BOOT diario `c5d3b939…` verificado.
- **Video decodificado con `0337`** (kernel `perf5` = perf4 + 0337, 0 LSE, `f590d561…`, `herovideoalign=1`): el reproductor llegó a `ready=1` y el reloj avanzó durante los 45 s con siete vueltas del clip (`loops=7`). mediaserverd no tuvo ningún crash y el decodificador creó superficies 420v nuevas con paso 320/320. La captura se tomó después de terminar la reproducción, así que en el teléfono no se comprobó ningún cuadro visible. Drop de control restaurado y verificado.
- **BOOT diario `ea87dc69…`** (kernel perf5, ADT 3058 MiB, línea diaria + `herovideoalign=1`), verificado por lectura. Copia en `s7-setup/idma-ab/approved-750p-3058m-perf5-video-daily.img`. Para volver atrás: `c5d3b939…` (perf3), `054157f5…` (3058 MiB, CI) y `3f9c0da1…` (2 GiB). El teléfono quedó en TWRP.
- YouTube en Safari con el BOOT `ea87dc69…`: los Shorts se reproducen (el usuario vio la imagen). Los vídeos normales muestran «Sorry, there was an error licensing this video». Log `s7-setup/perf-work/youtube-boot1`: `lskdd` arrancó y salió 772 veces (`xstat 0xff595c00`) y `fairplayd.H2` 108 veces (sale con 0 al instante). Son los servicios FairPlay, que dependen de hardware de Apple que el S7 no tiene. WebKit tiene las preferencias `WebKitEncryptedMediaAPIEnabled` y `LegacyEncryptedMediaAPIEnabled`. Hipótesis sin verificar: si Safari no ofrece EME/FairPlay, YouTube debería servir las secuencias sin DRM.
- Audio: la tabla del códec CS47L91 se capturó con Linux reproduciendo por el altavoz y el auricular. OUT3 (auricular) mezcla AIF1RX1/2 (0x6a0/0x6a2) y AIF4TX alimenta el MAX98506. El usuario lo describe como sonido «por el canal de llamada». `0338` (`heroearpiece=0`) quita las fuentes de OUT3 y lo silencia. Kernel `perf6` = perf5 + 0338, 0 LSE, `5da76b9c…`. BOOT de prueba `cbaa8399…` (línea diaria + `herovideoalign=1 heroearpiece=0 herotwrp=600`) escrito y verificado. El usuario escucha. El BOOT diario `ea87dc69…` está en el PC para restaurar.
- Audio `0339`: registro 0x2D del MAX98506 (DAC_IN_SEL [6:5], SPK_GAIN [4:0]) con `heroampgain` y `heroampsum`. Kernel `perf7` = perf6 + 0339, 0 LSE, `96ab2212…`. BOOT de prueba `923c84ca…` (línea diaria + `herovideoalign=1 heroearpiece=0 heroampsum=1 heroampgain=24 herotwrp=600`). El log muestra `HEROLTE AUDIO: amplifier gain 24, L+R, 0x2d=0x58`. Falta la opinión del usuario sobre el sonido.
- 60 fps, pruebas de deslizamiento solo BOOT con kernel perf7 (fps de movimiento calculado de los huecos entre fotogramas mostrados): base 49.0 (79% a un tick), `herogpu_flush=2` 49.0, `herogpu_flush=2` + 650 MHz GPU + 2288 MHz CPU 46.7. Anterior `swipe-new` 51.0. La GPU está ocupada un 12–13% y los envíos ya van por cola (`HERO_ASYNC=1`). Ni la caché de la GPU ni los relojes son el límite. Las pruebas seguidas calentaron el SoC de 44 a 54 °C, así que la última no es del todo comparable. backboardd solo recibe vsync (no hay aviso de swap completado), así que un fotograma de CPU de más de 16.7 ms pierde un tick. Siguiente paso: medir el tiempo por fotograma dentro de backboardd/QuartzCore (requiere cambiar `gl.env` en la zona de drop).
- `0340` (medición de fotogramas): para cada swap de backboardd el kernel cuenta el tiempo desde el tick de vsync anterior, el tiempo desde el swap anterior y el tiempo de trabajos de GPU entre ambos (`HEROLTE FRAME`). Kernel `perf8` = perf7 + 0340, 0 LSE, `87e9051c…`; BOOT de prueba `940ecc28…` (`heroswipe=1`). Deslizamiento con drop de control: 52.4 fps de movimiento. Entre swaps, la mayoría de intervalos son de 12–18 ms y un 25–30% de 18–25 ms. Esos son los ticks perdidos. GPU por fotograma: mediana de unos 4 ms, con cola hasta 8–16 ms. La "latencia tras el tick" es módulo del periodo, así que no sirve por sí sola.
- Mismo BOOT con `HERO_PROF=1` en `gl.env` (cambio del drop aprobado por el usuario; drop de control `f35a1e77…` restaurado y verificado): 50.9 fps. Durante el gesto: 34–39% de las muestras en `mach_msg2_trap` (el hilo de la cola esperando trabajos de GPU en el kernel y el IPC), QuartzCore 17–19%, libOSMesa 12–14%, `_platform_memmove` 3–13%, sin una función de Mesa por encima del 1%. Con `EAGL_SHIM_DEBUG=1` (46.5 fps; el modo debug frena): solo 19 subidas `texImageIOSurface` en el gesto (14 iconos de 120×120), así que el memmove no viene de las texturas. Las líneas PIPE no se imprimen con el lienzo de 750×1334: `pipe_count_sync` solo cuenta superficies ≥1000×2000. BOOT diario `ea87dc69…` y drop de control restaurados y verificados. El teléfono quedó en TWRP.
- `0341` (`herogpu_sleep=N`): un trabajo de GPU de un cliente se sondea 50 µs (`herogpu_spin`) y después el hilo duerme N µs entre sondeos en lugar de girar con `delay(10)`. Con 0 (por defecto) todo sigue igual. Kernel `perf9` = perf8 + 0341, 0 LSE, `7cf4e4c7…`. No hay ruta de interrupciones de la Mali en este kernel (solo IPI y temporizador), así que no se probó una espera por IRQ. Deslizamientos alternados, solo BOOT: base 46.6 / 51.6 / 50.6 (media 49.6), `herogpu_sleep=150` 51.8 / 47.4 / 47.3 (media 48.8), `herogpu_sleep=50` 47.4. Sin mejora. La variación entre ejecuciones iguales es de ±3 fps, así que una sola ejecución no basta para comparar. En la ejecución con 50 µs `gamed` cayó una vez (`esr 0x92000006`). Otros procesos de fondo fallan en todas las ejecuciones (9–14 líneas CRASH). Sin pánicos ni reinicios de GPU. BOOT diario `ea87dc69…` restaurado y verificado. El teléfono quedó en TWRP.
- El usuario confirma que el sonido con `heroampsum=1 heroampgain=24` (BOOT `923c84ca…`) es mejor. Nuevo **BOOT diario `20015cd0…`** (kernel perf7, ADT 3058 MiB, línea diaria + `herovideoalign=1 heroearpiece=0 heroampsum=1 heroampgain=24`, sin `herotwrp`), verificado por lectura. Copia en `s7-setup/idma-ab/approved-750p-3058m-perf7-amp-daily.img`. Para volver atrás: `ea87dc69…` (perf5, vídeo). El teléfono quedó en TWRP.
- `0342` (estado del cargador) y `0343` (motor de vibración, candado del buzón APM). Kernel `perf10` = perf9 + 0342 + 0343, 0 LSE, `ee16d4fe…`. BOOT de prueba `b12408e1…` (`herovib=300`, `herotwrp=180`). Todos los registros del cargador leídos en 0x66 devolvieron 0xff (`HEROLTE CHG: int_ok 0xff dtls 0xff/0xff/0xff …`), así que `external=1` era un falso positivo. TWRP muestra `max77854-charger` como `1-0066` en el bus 13650000 junto a los dummies 0x25, 0x26, 0x36, 0x69 y 0x72. `max77854-private.h` asigna el cargador a 0xD2 (7 bits 0x69). 0x66 es la página PMIC/háptica. Motor: `LDO34 0x7c`, `PWM tcfg0 0xc41 tcon 0x500408`. El temporizador 1 cuenta a 399450 Hz con el preescalador 65 que deja el bootloader. La comprobación de ≥1 MHz lo rechazó (`the PWM timer does not run, no vibration`), así que no se escribió nada en la página háptica. El inversor del temporizador 1 (TCON bit 10) ya estaba activo. Sin pánico. BOOT diario `20015cd0…` restaurado y verificado.
- **Batería:** iOS descargó a −1309 mA y bajó de 2% a 1%. Sin un driver de cargador, iOS no carga, y con el telefono a 1% no se hacen más arranques de prueba. TWRP marcaba `Charging`, +438 mA y 3.72 V. El teléfono queda en TWRP cargando.
- Vibración en iOS 16 (caché compartido, MediaExperience): `FigVibrator_IOKit.c` se usa cuando libVibeSynthEngine dice que no hay hardware háptico. Llama a `IOServiceGetMatchingService(IOServiceNameMatching("vibrator"))` y luego a `IORegistryEntrySetCFProperties` con `hertz_millisecs` = [{`intensity`: 16.16}, ms encendido, booleano, ms apagado] y `repeat`. Para parar envía otro `hertz_millisecs` con `repeat` falso. La misma búsqueda decide si el aparato tiene vibrador. mediaserverd, que contiene ese código, se ejecuta en el S7. `0344`: cargador en 0x69, preescalador 0 del PWM (timers 0/1; el timer 0 está parado) conservando el inversor, patrones encendido/apagado/repetir con intensidad, y un IOService `SweetVibrator` con nombre `vibrator` que registra los primeros diccionarios (`SWEET VIBRATOR:`). Falta probarlo cuando la batería tenga carga.
- Kernel `perf11` = perf10 + `0344`, 0 LSE, `2dbb8b74…`. BOOT de prueba `019ee208…` (`herovib=300`, `herotwrp=180`) tras cargar en TWRP de 2% a 15% en 38 min. `SWEET VIBRATOR: registered`. Cargador en 0x69: `pmic id 0x54, int_ok 0xdd dtls 0x60/0x31/0 cnfg_00 0x5, charge 2100 mA (cnfg_02 0x6a), input 450 mA (cnfg_09 0xf)`, es decir VBUS válido y carga en corriente constante, con el límite de entrada de 450 mA. iOS pasó de +40 mA a −1552 mA con la pantalla activa, así que con ese límite el consumo supera la entrada USB. Motor: el temporizador 1 cuenta a 25991287 Hz con el preescalador 0, `MAINCTRL1 0x87`, `MCONFIG 0 -> 0x82: ready`, tres pulsos de 300 ms enviados (`state 1`). Falta que el usuario confirme si se sintieron. Ningún proceso de iOS llamó todavía a `setProperties` del servicio `vibrator`. Sin pánico. BOOT diario `20015cd0…` restaurado y verificado. El teléfono quedó en TWRP con 14%. Imagen `dim11.img` `7b432364…` (perf11 + `heropanelid=1 heropaneldim=1`) preparada para la prueba AOR con el usuario mirando la pantalla.
- El usuario no estaba presente durante la prueba vib11, así que sigue sin confirmarse si el motor vibró.
- `0345`: registro de todos los SOC del medidor (`HEROLTE FG: rep/vf/mix/av, ocv, cap, cycles`) cada 5 minutos. Lectura del MUIC (página 0x4A, 7 bits 0x25; STATUS2 0x05 CHGTYP [2:0]). Con cargador dedicado o CDP, `herochgin` (1500 mA por defecto, 0 lo desactiva) sube el límite CHGIN (CNFG_09, pasos de 33.3 mA como en el driver de Samsung, tras abrir CHGPROT en CNFG_06). El puerto de PC no se toca. Corrige la escala del registro: 0x0f son 500 mA, no 450. iOS recibe la temperatura del medidor y los ciclos en lugar de 25 °C y 0. `herochgdelay=N` informa el cable N segundos después del primer sondeo. Kernel `perf12` = perf11 + 0345, 0 LSE, `07a6a621…`.
- Prueba `chg12` (BOOT `1ac461dd…`, `herochgdelay=60`, `herotwrp=240`): `rep 69.99% vf 79.18% mix 71.89% av 70.39%, ocv 4072 mV`, `full 2578 nom 2534 design 2973 mAh, cycles 3.14`. El 15% anterior era el valor real de REPSOC. Tras cargar en TWRP el medidor coincide con TWRP (68–69%). `muic 0x1f/0x41/0 (type 1)`: puerto USB de PC, límite de 500 mA sin cambios, `cnfg_06 0xc` (CHGPROT ya abierto). A los 60 s: `cable reported after 60 s`. La captura muestra por primera vez el icono de batería con el rayo de carga en la barra de estado de iOS. Al conectar, iOS no vibró ni llamó a `setProperties` del servicio `vibrator`, lo esperable en un iPhone sin Taptic. Para probar la vibración desde iOS hace falta una acción del usuario, por ejemplo Ajustes > Sonidos > Tono > Vibración. Con el cable de PC iOS sigue descargando (−929 a −1229 mA). Fallos de fondo conocidos: assetsd, MusicCoreSpotlightExtension, driverkitd sig 9. BOOT diario `20015cd0…` restaurado y verificado. Imagen diaria propuesta `daily-perf12.img` `bf502939…` (mismos argumentos que `20015cd0…`), sin escribir.
- `0346`: carga por CPU desde la contabilidad de inactividad del planificador (`HEROLTE LOAD: busy %`, cada 60 s en el hilo de energía) y `herobattlog=1` (corriente en cada sondeo de 10 s). Kernel `perf13`, 0 LSE, `15999e90…`. Prueba `pwr13a` (300 s, sin deslizamientos, cable de PC): con la pantalla de inicio en reposo los cuatro núcleos pequeños seguían al 48–50% (`50 49 48 48 41 18 4 2`) y la corriente neta era −430 a −580 mA. Con `sweettop=1` (`pwr13b`) en cada muestra de 5 s aparecía `vmd 193%` y `launchd` ~70%. `vmd` es `com.apple.voicemail.vmd` (buzón de voz visual): sin telefonía gira en dos núcleos toda la sesión. bluetoothd y fairplayd.H2 salen con 0 y launchd los relanza unas 31 veces en 300 s. El límite de widgets (`herowidgetcap`) solo se aplicaba dentro del hilo de `sweettop`, que no está en la línea diaria, así que no actuaba en el BOOT diario.
- `0347`: el muestreador de procesos corre en cada arranque de HEROLTE y solo imprime con `sweettop`, así que el límite de widgets ahora actúa siempre. `vmd` se limita al 5% de un núcleo (`herovmdcap=N`, 0 lo desactiva) con `proc_set_task_ruse_cpu` THROTTLE. Kernel `perf14` = perf13 + 0347, 0 LSE, `20f950b2…`. Prueba `pwr14`: `HEROLTE CAP: vmd limited to 5%`, en reposo `all 16–47% of 800%` (antes 230–290%), vmd ~10%, launchd ~5%, carga por CPU `26 37 29 22 18 15 12 10`, corriente neta en reposo −180 a −330 mA (antes −240 a −450). No hubo pánicos.
- **BOOT diario `f00731d2…`** (kernel perf14 con 0342–0347, ADT 3058 MiB, misma línea diaria que `20015cd0…`), verificado por lectura. Copia en `s7-setup/idma-ab/approved-750p-3058m-perf14-vmdcap-daily.img`. Para volver atrás: `20015cd0…` (perf7). Este BOOT añade el estado de carga, el MUIC y el límite de 1500 mA con cargador de pared (sin probar con cargador), la temperatura del medidor, el servicio `vibrator` y el límite de vmd. Los scripts de prueba `run-*.ps1` todavía restauran `daily-perf7.img`. Para nuevas pruebas hay que cambiarlos a `daily-perf14.img`.
- Brillo en iOS 16 (caché compartido, CoreBrightness): `BCAppleBacklightBrtControl` busca su servicio con `IOServiceGetMatchingServices({IOPropertyMatch: {backlight-control: …}})` (0x1af0a2240). Lee `IODisplayParameters` (`brightness`, `BrightnessMilliNits`), `MinNits`/`MaxNits` y tablas opcionales (`NitsToUserBrightnessTable`, `backlight-marketing-table`). Otro camino fija el nivel con `IORegistryEntrySetCFProperty(<IOMobileFramebuffer>, "IOMFBBrightnessLevel", CFNumber)` (0x1af016810). `AppleCLCD` no tenía `setProperties`, así que esa llamada habría fallado con kIOReturnUnsupported.
- `0348`: `AppleCLCD::setProperties` acepta `IOMFBBrightnessLevel`, lo guarda (`herolte_bright_level` y la propiedad) y lo registra. `0349` (`herobacklight=1`, apagado por defecto): servicio `SweetBacklight` con `backlight-control`, `IODisplayParameters`, MinNits 2 y MaxNits 500, que registra cada `setProperties`. Kernels `perf15` (`9734f353…`) y `perf16` (`e445206d…`), 0 LSE. Prueba `bright15`: ninguna llamada `IOMFBBrightnessLevel` ni `setProperties` durante el arranque. Prueba `bl16`: `SWEET BACKLIGHT: registered (backlight-control)`, sin llamadas y sin crash de backboardd ni de SpringBoard. Sin los registros de usuario (os_log) no se sabe todavía si CoreBrightness encontró el servicio y lo rechazó. Siguiente paso: desensamblar `-[BCAppleBacklightBrtControl initWithService:]` o capturar os_log de backboardd. Después, con el usuario mirando la pantalla, la prueba AOR (`dim11.img`). BOOT diario `f00731d2…` restaurado y verificado tras ambas pruebas.
- Con el BOOT diario `f00731d2…` (perf14) el usuario confirmó que la vibración funciona desde iOS (Ajustes > Sonidos > Tono > Vibración). Es la ruta `FigVibrator_IOKit` → servicio `vibrator` → MAX77854 háptico con PWM. También notó que el teléfono se calienta algo menos con el límite de vmd.
