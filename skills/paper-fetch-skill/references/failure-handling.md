# 失败处理

先保存已返回的 manifest 与正文路径，读影响当前任务的 reason code 和诊断。失败或仅摘要/元数据返回 1；参数错误返回 2。批量部分成功可以独立读取，不依赖整批汇总完成。

身份歧义时依据候选消歧；限流遵守已有 provider 策略；challenge/auth_required 使用人工认证。profile 正常排队没有锁等待超时，也不消耗页面预算；外部占用与归属冲突按具体错误处理。

只针对影响任务的实际错误重试或说明，不自动切换用户指定来源，不绕过登录、验证码或付费墙，不追加范围外检查。

`auth_required` 对应 acceptance.fetch/overall 的 action_required；使用同一配置执行 `paper-fetch auth ams` 后再获取。认证失败或取消停止该 AMS 获取并保留 error 的原始 stage/reason，批量其他论文继续。先读回执的 target_satisfied、error 和原因码，再按需要打开 manifest。
