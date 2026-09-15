# 来源与参考

核对日期：2026-09-15。

| 来源 | 本工程中的角色 |
|---|---|
| 用户提供的 WakeUp 6.0.23 APK | 继承应用行为、类结构、资源与数据兼容层 |
| 用户提供的广告版 APK | 前序版本学校配置对照来源 |
| 用户提供的上大页面和作息说明 | 本地解析结构与 12 节作息规格 |
| 用户提供的上海大学校徽 | 启动品牌图片 |
| xianfei/WakeupSchedule_BUPT | 校园专属适配、作息定制与项目说明方式的参考 |
| Greasy Fork 上大相关脚本 | 教务导航及快捷入口的交互参考 |

## WakeupSchedule_BUPT

<https://github.com/xianfei/WakeupSchedule_BUPT>

该参考项目基于 WakeUp 3.621，README 列出北邮新教务、VPN、45 分钟作息和 14 节默认值等校园适配。项目采用 Apache-2.0，保留 YZune 署名。本工程参考其中的校园适配方向和清晰列举修改内容的方式。

本工程的应用基础版本为用户提供的 6.0.23，其继承部分的来源与授权单独记录在 `LICENSES/ORIGINS.md`。

## Greasy Fork

- 上大选课优化：<https://greasyfork.org/zh-CN/scripts/453887>。作者 yanthinkin，查阅版本 0.25，标注 MIT。其匹配站点包括 jwxk.shu.edu.cn。
- 上海大学网站增强 - 刷课助手：<https://greasyfork.org/zh-CN/scripts/434613>。作者 panghaibin，查阅版本 3.5.2，标注 MIT。

r5 采用原生快捷入口集中访问教务、课表与选课。选课提交及页面业务由学校原网页执行。上述脚本作为交互设计参考，项目内的入口由 `ShuPortal.java` 实现。

## Android 技术依据

- 启动主题与 SplashScreen：<https://developer.android.com/develop/ui/views/launch/splash-screen>
- Cookie 管理：<https://developer.android.com/reference/android/webkit/CookieManager>
- WebView 生命周期：<https://developer.android.com/reference/android/webkit/WebView>
- DEX 格式：<https://source.android.com/docs/core/runtime/dex-format>
- APK v2 签名：<https://source.android.com/docs/security/features/apksigning/v2>
- 应用签名：<https://developer.android.com/studio/publish/app-signing>
- 仓库授权说明：<https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository>
