# 构建与编辑

## 工具链

主入口 `build.py` 依次完成核心汇编、Java 扩展编译、资源编码、学校目录编码和 APK 打包。环境使用 JDK 21+、Python 3.10+ 和 `cryptography`。Java 扩展以 Java 8 class-file 格式生成，再由 `tools/jvm2dex.py` 编译为 DEX 035。

`tools/api-stubs` 只参与编译期符号解析；运行时引用由 Android 系统及继承核心提供。最终 APK 的 `classes3.dex` 来自 `app/src/main/java` 的 6 个顶层 Java 文件与其内部类。

```bash
python -m pip install -r requirements.txt
python build.py --test
```

构建输出在 `dist/`；中间文件与结果在 `build/`。单独测试已有产物：

```bash
python tests/run.py dist/WakeUp_6.0.23_SHU_r5.apk
```

## 签名

```bash
python build.py --keystore /private/update-signing.p12 --password-file /private/PASSWORD.txt --test
```

`--password-env` 支持指定环境变量名，默认使用 `WAKEUP_KEYSTORE_PASSWORD`。同一安装身份通过同一证书延续更新。原始密钥、密码文件和设备日志保存到工程目录以外。

构建器实现 ZIP 对齐、JAR v1 签名和 APK v2 签名。Java 独立验证器和 Python 验证器交叉核对签名；测试同时翻转内容字节检查篡改检测。

## Java 功能

| 文件 | 内容 |
|---|---|
| `shu/wakeup/Branding.java` | 启动品牌布局与一次性作息升级挂接 |
| `shu/wakeup/ShuTimes.java` | 上大 12 节时间和旧默认模板 |
| `shu/wakeup/ShuMigration.java` | SQLite 事务迁移和自定义值保留 |
| `shu/wakeup/ShuPortal.java` | 教务导航、Cookie 会话、网页生命周期 |
| `shu/wakeup/ShuImporter.java` | 上大个人课表表格解析 |
| `com/suda/yzune/wakeupschedule/DonateActivity.java` | 保持原组件名的教务入口 Activity |

修改新增功能后执行主构建即可生成扩展 DEX。涉及平台调用时，同步补充 API 签名并扩展宿主测试。更广的 Java 语言功能可在 `jvm2dex.py` 的指令映射处实现；当前编译器覆盖本工程所用的 Java 8 指令。

## 继承核心

通过 `core/dex1/CLASS_INDEX.json` 或 `core/dex2/CLASS_INDEX.json` 按完整类名找到汇编源文件。指令使用符号化的方法、字段和类型引用；跳转及异常处理使用标签。

修改方法体后，汇编器按新长度重排代码区，并调整类数据、注解、调试信息及映射表中的相关偏移。既有常量池、类和成员的身份由 `metadata` 布局维护；新类与新接口适合放到 Java 扩展层。构建器对超出当前编码宽度的结构修改给出明确的编译诊断。

## 资源

`app/src/main/resources/table.json` 是资源表的构建源；`resources/compiled/` 保存布局、菜单、动画及 Manifest 的带类型源文件。每个源文件包含字符串、资源编号、节点和类型化属性。`app/src/main/res-views` 及顶层 Manifest 提供 XML 阅读视图。

实际图片位于 `app/src/main/res`。文件路径到 APK 条目的对应关系见 `config/package.json`。原始资源名存在大小写变体时，工程文件增加数字前缀，兼容 Windows 文件系统；APK 内路径保留原值。资源编号、符号名、配置和文件路径的检索表见 `config/resource-index.json`。

修改文本资源的例子：

```bash
python tools/resource_text.py app_name "WakeUp_SHU"
python build.py --test
```

直接编辑某个布局的 `resources/compiled/*.json`，再执行 `python tools/refresh_views.py` 更新阅读视图。类型值使用 Android `Res_value` 规范：`type=3` 表示字符串索引，`type=1` 表示资源引用，尺寸与颜色保留其 Android 编码。

## 学校与作息

`config/schools.json` 为学校目录的编辑源，主构建按继承解析器的格式编码。

`config/shu.json` 为作息规格与测试基准；运行实现分别位于 `ShuTimes.java` 和核心 DAO 的默认时间表工厂。修改作息时同步维护这三处，测试会核对 12 条默认工厂指令与规格一致。

## 可重复构建记录

r5 的原始打包与源工程重建各完成一次签名构建，APK 字节相同。该记录对应当前源码、当前工具链和同一签名密钥。工具升级后的输出以新一轮构建比较记录为准。
