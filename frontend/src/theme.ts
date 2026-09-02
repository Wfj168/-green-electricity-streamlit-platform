import { theme, type ThemeConfig } from "antd";

export const appTheme: ThemeConfig = {
  algorithm: theme.darkAlgorithm,
  token: {
    colorPrimary: "#27c2ff",
    colorInfo: "#27c2ff",
    colorSuccess: "#35d07f",
    colorWarning: "#f6b84b",
    colorError: "#ff6b57",
    colorBgBase: "#031326",
    colorBgContainer: "#071f38",
    colorBgElevated: "#0a2947",
    colorBorder: "#164d72",
    colorText: "#ecf7ff",
    colorTextSecondary: "#91acc2",
    borderRadius: 6,
    fontFamily: '"Microsoft YaHei", "PingFang SC", sans-serif',
    controlHeight: 34,
    fontSize: 13,
    fontSizeSM: 12,
  },
  components: {
    Layout: { bodyBg: "#031326", headerBg: "#04172b", siderBg: "#04182d" },
    Menu: {
      darkItemBg: "#04182d",
      darkItemSelectedBg: "#0a3a61",
      darkSubMenuItemBg: "#031326",
      itemBorderRadius: 5,
    },
    Table: {
      headerBg: "#0a2947",
      headerColor: "#b9d6e9",
      rowHoverBg: "#0b2d4d",
      borderColor: "#123b5a",
    },
  },
};
