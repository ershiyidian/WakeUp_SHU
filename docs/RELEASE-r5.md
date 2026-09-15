# WakeUp_SHU 6.0.23 / r5

## 安装

安装包：WakeUp_6.0.23_SHU_r5.apk
应用名称：WakeUp_SHU
包名：com.suda.yzune.wakeupschedule
versionName：6.0.23
versionCode：267
文件大小：11,484,842 字节（约 11.48 MB）

r5 沿用 r4 的更新证书，适合直接覆盖安装，继续使用现有课表及设置。课程备份适合同时保存在系统下载目录。

## 启动标识

系统启动主题和应用内启动布局共同使用 WakeUp 图标与上海大学校徽的组合标识。系统启动主题已指定组合图、背景和底部文字图，分别提供浅色与深色资源。底部文字为：

仅供学习使用，请在下载后24小时内删除

冷启动、温启动由系统呈现启动主题；返回后台已打开的课表时延续当前界面。桌面启动图标保留 WakeUp 原图。

## 功能入口

原赞助弹窗和付费说明已移除。原高级设置整理为普通“功能设置”，已有功能入口保持可用。主界面和原捐赠菜单接入“上大教务”。时钟保留在教务入口的快捷栏。

## 教务与登录会话

“上大教务”提供：教务首页、个人课表、选课系统、导入课表、功能设置、登录管理、时钟。

教务首页：https://jwxt.shu.edu.cn/
选课系统：https://jwxk.shu.edu.cn/

首先在教务首页完成统一身份认证，再进入个人课表。选课入口打开学校原页面，由用户在学校界面完成操作。

教务页与原课表导入页共用应用内 WebView Cookie 存储；退出页面时释放 WebView，保留会话 Cookie。学校的 Cookie 域、有效期和服务端登录策略决定实际会话持续时间。

“登录管理 → 清除登录状态”清理当前应用内浏览器的 Cookie 和 WebStorage，随后返回教务首页，适合切换账号。

导入顺序：教务首页 → 统一认证 → 个人课表 → 选择学年和学期 → 查询 → 表格视图 → 导入课表。

## 上大默认作息

| 节次 | 上课 | 下课 |
|---:|---|---|
| 1 | 08:00 | 08:45 |
| 2 | 08:55 | 09:40 |
| 3 | 10:00 | 10:45 |
| 4 | 10:55 | 11:40 |
| 5 | 13:00 | 13:45 |
| 6 | 13:55 | 14:40 |
| 7 | 15:00 | 15:45 |
| 8 | 15:55 | 16:40 |
| 9 | 18:00 | 18:45 |
| 10 | 18:55 | 19:40 |
| 11 | 20:00 | 20:45 |
| 12 | 20:55 | 21:40 |

每节 45 分钟，默认显示 12 节。新建时间表直接使用上述模板。升级时，前 12 条时间与旧默认模板完全匹配的时间表转为上大作息，原默认 50 分钟 / 20 节配置调整为 45 分钟 / 12 节。手动调整过的时间表及其他自定义配置保留原值。原有课程、周次、教师、地点和课表关联继续保留。

## 源码工程

工程采用 Java 扩展、逐类 DEX 汇编核心与带类型资源源文件组织。构建器从工程文件重建全部 DEX、资源表、布局、Manifest 与 APK。

- app/src/main/java：上大启动、教务导航、作息迁移、课表解析的 6 个顶层 Java 文件。
- core：继承的 6.0.23 核心按类整理为 .dexasm.json，含指令、寄存器、符号引用、分支和异常处理；元数据另行分类。
- app/src/main/resources、res、res-views：资源构建源、图像及 XML 阅读视图。
- config：学校目录、作息规格、资源索引和打包配置。
- tools、tests：编译、汇编、资源编码、签名与回归测试。
- README、docs、LICENSES：安装、构建、架构、会话、测试、来源和授权说明。

新增 Java、构建工具和测试采用 MIT。继承的 6.0.23 代码、原资源和学校标识按各自权利来源管理，继承部分的公开再分发授权列为发布前确认项。工程的源码形式与授权范围分别在 README 和 LICENSES/ORIGINS.md 中说明。

项目明确参考 xianfei/WakeupSchedule_BUPT 的校园适配、作息定制与说明方式。教务导航参考 Greasy Fork 的“上大选课优化”和“上海大学网站增强 - 刷课助手”。对应作者、链接和授权信息列于 docs/SOURCES.md。

## 构建

环境：JDK 21+、Python 3.10+、cryptography。

```bash
python -m pip install -r requirements.txt
python build.py --test
```

生成 dist/WakeUp_SHU-unsigned.apk。使用私有 PKCS#12 证书构建签名包：

```bash
python build.py --keystore /private/update-signing.p12 --password-file /private/PASSWORD.txt --test
```

签名密钥保存在工程之外。覆盖更新继续使用同一证书。

## 已执行的验证

本轮从整理后的源码工程完整重建并签名，重建 APK 与交付 r5 逐字节一致。

验证环境：Linux、JVM、Python。Android 生命周期、数据库与界面调用的宿主测试采用显式替身；实际解析和作息迁移 DEX 同时由宿主指令解释器执行。

| 项目 | 结果 |
|---|---|
| 3 个 DEX 结构与类数据所属关系 | 通过 |
| 选定方法的异常路径与基本类型检查 | 66 个方法通过 |
| 新代码成员链接与 final 继承检查 | 204 项通过 |
| 上大解析 Java / APK 内 DEX 执行 | 各 25 项断言通过 |
| 作息迁移 Java / APK 内 DEX 执行 | 各 77 项断言通过 |
| Android 资源编解码往返 | 789 项逐字节一致 |
| 资源文件引用 | 999 项存在 |
| 汇编方法长度变化后重新构建 | 通过 |
| 源文件路径大小写兼容检查 | 通过 |
| APK v1 / v2 签名、篡改负对照 | 通过 |

测试数据使用合成课表与示例教师。完整报告位于 tests/reference-report.json。

手机验收项：一加 12 / ColorOS 16 的开屏视觉、作息升级、入口导航、统一认证、选课页面、导入保存、锁屏提醒和长期资源占用。32 位、64 位设备分别列入运行验收；打包代码使用通用 DEX。

## 文件核对

APK SHA-256：3f08c859d42408a89f53db1b2f89447ed455119acb0bd9522d871fe024f71bd2
更新证书 SHA-256：df99b96d8a36ef823dcb43705a949f8b407221dc31601fb57c7bb77fe99ec364

## 技术与项目参考

- BUPT 参考项目：https://github.com/xianfei/WakeupSchedule_BUPT
- 上大选课优化：https://greasyfork.org/zh-CN/scripts/453887
- 上海大学网站增强：https://greasyfork.org/zh-CN/scripts/434613
- Android 启动主题：https://developer.android.com/develop/ui/views/launch/splash-screen
- Android CookieManager：https://developer.android.com/reference/android/webkit/CookieManager
- GitHub 授权说明：https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository
