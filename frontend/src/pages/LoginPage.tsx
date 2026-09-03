import { LockOutlined, ThunderboltOutlined, UserOutlined } from "@ant-design/icons";
import { Alert, Button, Form, Input } from "antd";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { v2Api } from "../services/api";
import { saveSession } from "../services/session";

export function LoginPage() {
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string>();
  const login = async (values: { username: string; password: string }) => {
    setSubmitting(true);
    setError(undefined);
    try {
      saveSession(await v2Api.login(values.username, values.password));
      navigate("/app/overview");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "登录失败");
    } finally {
      setSubmitting(false);
    }
  };
  return (
    <main className="login-page">
      <div className="login-grid" />
      <div className="login-stage">
        <section className="login-branding">
          <div className="login-logo"><ThunderboltOutlined /></div>
          <h1>零碳农业园区规划与调度</h1>
          <p>绿电直连 · 农业柔性负荷 · 储能优化 · 碳排溯源</p>
        </section>
        <section className="login-panel">
          <div className="login-panel-brand"><ThunderboltOutlined /><div><strong>平台登录</strong><span>融合版 V2</span></div></div>
          <Alert className="login-alert" type={error ? "error" : "info"} showIcon message={error ?? "生产环境启用账号密码与令牌认证；公开演示可由部署配置决定是否要求登录。"} />
          <Form layout="vertical" onFinish={login}>
            <Form.Item name="username" label="账号" rules={[{ required: true, message: "请输入账号" }]}>
              <Input prefix={<UserOutlined />} placeholder="请输入账号" autoComplete="username" />
            </Form.Item>
            <Form.Item name="password" label="密码" rules={[{ required: true, message: "请输入密码" }]}>
              <Input.Password prefix={<LockOutlined />} placeholder="请输入密码" autoComplete="current-password" />
            </Form.Item>
            <Button block type="primary" htmlType="submit" loading={submitting}>登录平台</Button>
          </Form>
        </section>
      </div>
    </main>
  );
}
