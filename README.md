# WakeUp_SHU

[中文版](README.zh-CN.md)

A customized WakeUp 6.0.23 build for Shanghai University: SHU academic-affairs integration, timetable import, 12-period schedule, dark-mode timetable, and lightweight startup.

**Current version: 6.0.23 / r5 · versionCode 267 · Android API 21+ · targetSdk 35**

## Getting Started

Install `WakeUp_6.0.23_SHU.apk` directly (if a newer WakeUp is already installed, clear its data/cache or uninstall and reinstall first).

The **上大教务 (SHU Academic Affairs)** entry on the main timetable gives you the academic homepage, personal timetable, course selection, timetable import, feature settings, login management, and clock. Keep the first entry of the school directory as "上海大学（新教务·推荐）" (Shanghai University, new academic system, recommended).

On first use, follow this order:

**教务首页 → 学校统一身份认证 → 个人课表 → 选择学年、学期 → 查询 → 表格视图 → 导入课表。**

The academic homepage is <https://jwxt.shu.edu.cn/> and course selection is at <https://jwxk.shu.edu.cn/>. Course selection itself happens on the school's original pages.

## Project Layout

The project is organized as **Java extensions + per-class DEX-assembled core + typed resource sources**. The build reads these sources directly and produces the APK.

```text
WakeUp_SHU/
├── app/src/main/
│   ├── java/                 # readable Java sources for SHU features
│   ├── resources/            # typed sources for the Android resource table, layouts, Manifest
│   ├── res/                  # images, icons, and other raw resources
│   ├── res-views/            # layout XML reading views
│   ├── assets/               # school directory, in-app resources
│   └── AndroidManifest.xml   # Manifest reading view
├── core/
│   ├── dex1/                 # 8,403 inherited core classes, assembled per class
│   └── dex2/                 # 2 assembled classes bridging startup and parsing
├── config/                   # plaintext school directory, period specs, packaging manifest
├── artwork/                  # SHU emblem and combined marks
├── tools/                    # assembler, Java→DEX compiler, resource encoder, signer
│   └── api-stubs/            # platform and core API signatures for extension builds
├── tests/                    # synthetic timetables, migration doubles, real DEX execution, structural tests
├── docs/                     # architecture, build, session, test, and provenance notes
├── LICENSES/                 # license notes by provenance
├── .github/workflows/        # manually triggered build workflow
├── build.py                  # main build entry
└── README.md
```

Inherited core keeps the 6.0.23 package's class names, obfuscated names, member signatures, and resource IDs. Each `.dexasm.json` file lists registers, instructions, literals, symbol references, branch labels, and exception handling. `CLASS_INDEX.json` maps fully qualified class names to files; numeric prefixes also tolerate case-folding filesystems.

`core/*/metadata` holds compiler layout, constant pools, annotations, and debug metadata. Method instructions are rebuilt from the per-class assembly files. New features compile from `app/src/main/java` into `classes3.dex`.

Source availability and license scope are recorded separately: **new Java, build tools, and tests are MIT; inherited 6.0.23 code, original resources, and school marks follow their respective rights holders. Redistribution rights for the inherited parts have not been obtained — do not redistribute this repository's release packages.** See [授权与来源](LICENSES/ORIGINS.md) (in Chinese).

## Build

Environment: **JDK 21+, Python 3.10+, cryptography**. The current build record uses the in-repo Java→DEX compiler and resource encoder. Everything needed for a full build is in this project.

```bash
python -m pip install -r requirements.txt
python build.py --test
```

Output: `dist/WakeUp_SHU-unsigned.apk`. Signed builds use your own PKCS#12 key:

```bash
python build.py --keystore /private/update-signing.p12 \
  --password-file /private/PASSWORD.txt --test
```

Windows PowerShell builds the same way via `python build.py`; multi-line arguments can go on one line. You can also put the password in the `WAKEUP_KEYSTORE_PASSWORD` environment variable and then just use `--keystore`.

Default signed output: `dist/WakeUp_6.0.23_SHU_r5.apk`. Overlay updates for existing users keep the original modded certificate; keys live outside the repository in a private location.

Details: [构建与编辑](docs/BUILD.md) (in Chinese).

## References & Thanks

**This project follows the campus-specific adaptation, period customization, and engineering-notes approach of [xianfei/WakeupSchedule_BUPT](https://github.com/xianfei/WakeupSchedule_BUPT).** That reference project targets WakeUp 3.621, is Apache-2.0, and retains YZune's attribution.

The academic-affairs entry interactions reference Greasy Fork's [上大选课优化](https://greasyfork.org/zh-CN/scripts/453887) (yanthinkin, MIT) and [上海大学网站增强 - 刷课助手](https://greasyfork.org/zh-CN/scripts/434613) (panghaibin, MIT). r5 implements the same navigation ideas as native shortcut entries; course selection itself stays on the school's pages.

Thanks to the original WakeUp author, the authors above, and all open-source dependencies. Full provenance and version ranges: [SOURCES](docs/SOURCES.md) (in Chinese).
