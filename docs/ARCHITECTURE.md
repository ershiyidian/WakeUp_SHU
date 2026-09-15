# 架构

## 应用层

`SplashActivity` 调用 `Branding.show`，首先完成旧默认作息的一次性升级，再交给原启动流程进入课表。系统启动窗口由 `SplashTheme` 的 `windowSplashScreenAnimatedIcon`、`windowSplashScreenBrandingImage` 和背景资源负责。

主课表、提醒、桌面组件、备份、周次显示与原有导入框架继承 6.0.23。r5 主界面把教务导航前置，原来的时钟放入同一导航入口。功能设置直接进入 `AdvancedSettingsActivity` 的原有功能项。

## 教务会话

`ShuPortal` 创建按需 WebView。首次入口为教务根网址；登录、验证码和认证状态由学校网页处理。个人课表按钮在教务域且登录表单消失时进入课表页。选课按钮打开学校选课站点；浏览器按域名和有效期处理 Cookie。

导入按钮启动原 `LoginWebActivity`，传入当前课表 ID、学校名称、`zf` 类型和教务根地址。两条界面路径共用同一应用的 WebView Cookie 存储。

## 源代码形式

核心部分逐类组织为 `.dexasm.json`；编译扩展保留 Java 源码；资源保留类型和配置。核心方法中的每条指令都在汇编源文件中，布局元数据负责常量池与编译结构的位置关系。构建时先生成代码布局骨架，再填入汇编结果并重定位。

`core/dex1/classes/app` 集中 WakeUp 的应用业务；`androidx`、`kotlin` 与 `libraries` 保存依赖的继承部分。文件名前缀具有唯一编号。类名、父类与路径的完整检索由 `CLASS_INDEX.json` 提供。

## 运行资源

教务 WebView 在进入页面时创建，退出时按停止加载、解除回调、从父布局移除、销毁的顺序释放。会话信息保留于应用的 WebView 存储。课表与组件继续采用原渲染路径；运行时编译优化由设备 ART 按实际使用生成。

系统资源需求由实际页面、WebView 版本和设备决定。性能验收以相同课表、相同壁纸和相同使用步骤的 PSS、CPU、帧耗时为比较条件。
