# WakeUp_SHU

面向上海大学的 WakeUp 6.0.23 定制工程：上大教务、课表导入、12 节作息、深色课表与轻量启动。

**当前版本：6.0.23 / r5 · versionCode 267 · Android API 21+ · targetSdk 35**

## 开始使用

直接安装 `WakeUp_6.0.23_SHU.apk`（已有新版本WakeUp需要首先 清除数据/缓存 或 卸载重装）。

主课表的 **上大教务** 入口提供「教务首页、个人课表、选课系统、导入课表、功能设置、登录管理、时钟」。学校目录第一项保持「上海大学（新教务·推荐）」。

首次访问按以下顺序操作：

**教务首页 → 学校统一身份认证 → 个人课表 → 选择学年、学期 → 查询 → 表格视图 → 导入课表。**

教务首页为 <https://jwxt.shu.edu.cn/>，选课入口为 <https://jwxk.shu.edu.cn/>。选课操作在学校原页面完成。

## 工程组织

本工程采用 **Java 扩展 + 逐类 DEX 汇编核心 + 带类型的资源源文件** 组织。构建过程直接读取这些源文件并生成 APK。

```text
WakeUp_SHU/
├── app/src/main/
│   ├── java/                 # 上大功能的可读 Java 源码
│   ├── resources/            # Android 资源表、布局与 Manifest 的带类型源文件
│   ├── res/                  # 图片、图标等原始资源
│   ├── res-views/            # 布局 XML 阅读视图
│   ├── assets/               # 学校目录、应用内资源
│   └── AndroidManifest.xml   # Manifest 阅读视图
├── core/
│   ├── dex1/                 # 8,403 个继承核心类，逐类汇编
│   └── dex2/                 # 启动与解析桥接的 2 个汇编类
├── config/                   # 学校明文目录、作息规格、打包清单
├── artwork/                  # 上大校徽和组合标识
├── tools/                    # 汇编器、Java→DEX 编译、资源编码、签名
│   └── api-stubs/            # 扩展编译时的平台与核心 API 签名
├── tests/                    # 合成课表、迁移替身、实际 DEX 执行、结构测试
├── docs/                     # 架构、构建、会话、测试与来源说明
├── LICENSES/                 # 按来源划分的授权说明
├── .github/workflows/        # 手动触发的构建流程
├── build.py                  # 主构建入口
└── README.md
```

继承核心保留 6.0.23 包中的类名、混淆命名、成员签名和资源编号。每个 `.dexasm.json` 文件列出寄存器、指令、字面量、符号引用、分支标签及异常处理。`CLASS_INDEX.json` 将完整类名映射到文件；数字前缀同时兼容大小写折叠的文件系统。

`core/*/metadata` 保存编译器布局、常量池、注解与调试元数据。方法指令从逐类汇编文件重建。新增功能由 `app/src/main/java` 编译到 `classes3.dex`。

源码提供范围与授权范围分别记录：**新增 Java、构建工具及测试采用 MIT；继承的 6.0.23 代码、原资源与学校标识按各自权利来源管理。继承部分的公开再分发授权列为发布前确认项。** 详见 [授权与来源](LICENSES/ORIGINS.md)。

## 构建

环境：**JDK 21+、Python 3.10+、cryptography**。当前构建记录使用仓库内的 Java→DEX 编译器与资源编码器。完整构建所需的代码和资源均在本工程中。

```bash
python -m pip install -r requirements.txt
python build.py --test
```

产物：`dist/WakeUp_SHU-unsigned.apk`。签名构建使用自己的 PKCS#12 密钥：

```bash
python build.py --keystore /private/update-signing.p12 \
  --password-file /private/PASSWORD.txt --test
```

Windows PowerShell 同样通过 `python build.py` 构建；多行参数可写为一行。也可将密码放入 `WAKEUP_KEYSTORE_PASSWORD` 环境变量，然后使用 `--keystore`。

签名后的默认产物：`dist/WakeUp_6.0.23_SHU_r5.apk`。现有用户的覆盖更新沿用原修改版证书；密钥保存在仓库外的私有位置。

详细步骤：[构建与编辑](docs/BUILD.md)。


## 参考与致谢

**本项目参考了 [xianfei/WakeupSchedule_BUPT](https://github.com/xianfei/WakeupSchedule_BUPT)** 的校园专属适配、作息定制与工程说明方式。该参考项目基于 WakeUp 3.621，采用 Apache-2.0，并保留 YZune 的署名。

教务入口交互参考了 Greasy Fork 的 [上大选课优化](https://greasyfork.org/zh-CN/scripts/453887)（yanthinkin，MIT）与 [上海大学网站增强 - 刷课助手](https://greasyfork.org/zh-CN/scripts/434613)（panghaibin，MIT）。r5 将相应导航思路实现为原生快捷入口，页面上的选课操作交由学校界面处理。

感谢 WakeUp 原作者、上述项目作者与各开源依赖的贡献。完整来源和版本范围见 [SOURCES](docs/SOURCES.md)。
