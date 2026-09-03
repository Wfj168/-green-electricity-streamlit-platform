import { useEffect, useMemo, useState } from "react";
import {
  AppstoreOutlined,
  AuditOutlined,
  BellOutlined,
  CalendarOutlined,
  CloudOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  FundProjectionScreenOutlined,
  HddOutlined,
  LineChartOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  PieChartOutlined,
  RadarChartOutlined,
  SettingOutlined,
  ThunderboltOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { Avatar, Badge, Breadcrumb, Button, Dropdown, Layout, Menu, Select } from "antd";
import dayjs from "dayjs";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  findGroupByPage,
  findPageByPath,
  navigation,
  overviewPage,
} from "../config/navigation";
import { clearSession, readSession } from "../services/session";

const { Header, Sider, Content } = Layout;

const groupIcons: Record<string, React.ReactNode> = {
  monitoring: <RadarChartOutlined />,
  production: <AppstoreOutlined />,
  forecast: <LineChartOutlined />,
  dispatch: <CalendarOutlined />,
  planning: <FundProjectionScreenOutlined />,
  assets: <HddOutlined />,
  carbon: <PieChartOutlined />,
  data: <DatabaseOutlined />,
  reports: <AuditOutlined />,
  system: <SettingOutlined />,
};

export function AppShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);
  const session = readSession();
  const [now, setNow] = useState(dayjs());
  const currentPage = findPageByPath(location.pathname) ?? overviewPage;
  const currentGroup = findGroupByPage(currentPage);
  const [openKeys, setOpenKeys] = useState<string[]>(currentGroup ? [currentGroup.key] : []);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(dayjs()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (currentGroup && !collapsed) setOpenKeys([currentGroup.key]);
  }, [currentGroup, collapsed]);

  const menuItems = useMemo(
    () => [
      {
        key: overviewPage.path,
        icon: <DashboardOutlined />,
        label: <Link to={overviewPage.path}>{overviewPage.title}</Link>,
      },
      ...navigation.filter((group) => group.key !== "system" || !session || ["admin", "auditor"].includes(session.role)).map((group) => ({
        key: group.key,
        icon: groupIcons[group.key],
        label: group.title,
        children: group.pages.map((page) => ({
          key: page.path,
          label: (
            <Link className="menu-link" to={page.path}>
              <span>{page.title}</span>
              {page.badge ? <Badge count={page.badge} size="small" /> : null}
            </Link>
          ),
        })),
      })),
    ],
    [session?.role],
  );

  const breadcrumbs = currentGroup
    ? [
        { title: <Link to={overviewPage.path}>态势总览</Link> },
        { title: currentGroup.title },
        { title: currentPage.title },
      ]
    : [{ title: currentPage.title }];

  return (
    <Layout className="app-shell">
      <Sider className="app-sider" width={226} collapsedWidth={72} collapsed={collapsed} trigger={null}>
        <div className="brand">
          <div className="brand-mark"><ThunderboltOutlined /></div>
          {!collapsed ? (
            <div className="brand-copy">
              <strong>零碳农业园区</strong>
              <span>规划与调度</span>
            </div>
          ) : null}
        </div>
        <Menu
          mode="inline"
          theme="dark"
          selectedKeys={[currentPage.path]}
          openKeys={collapsed ? [] : openKeys}
          onOpenChange={(keys) => {
            const latest = keys.find((key) => !openKeys.includes(key));
            setOpenKeys(latest ? [latest] : []);
          }}
          items={menuItems}
          className="app-menu"
        />
      </Sider>
      <Layout>
        <Header className="app-header">
          <div className="header-left">
            <Button
              type="text"
              className="collapse-button"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setCollapsed((value) => !value)}
              aria-label={collapsed ? "展开菜单" : "收起菜单"}
            />
            <Select
              className="park-select"
              value="示范园区"
              options={[{ value: "示范园区", label: "零碳农业示范园区" }]}
              aria-label="选择园区"
            />
            <span className="header-chip"><CloudOutlined /> 当前数据：可追溯演示基准</span>
          </div>
          <div className="header-right">
            <span className="clock">{now.format("YYYY-MM-DD HH:mm:ss")}</span>
            <Badge dot><Button type="text" icon={<BellOutlined />} aria-label="告警" /></Badge>
            <Dropdown
              menu={{
                items: [
                  { key: "profile", label: "个人中心" },
                  { key: "logout", label: "退出登录", danger: true, onClick: () => { clearSession(); navigate("/login"); } },
                ],
              }}
            >
              <button className="user-button"><Avatar size="small" icon={<UserOutlined />} /><span>{session?.displayName ?? "演示管理员"}</span></button>
            </Dropdown>
          </div>
        </Header>
        <div className="app-breadcrumb-bar"><Breadcrumb items={breadcrumbs} /></div>
        <Content className="app-content"><Outlet /></Content>
      </Layout>
    </Layout>
  );
}
