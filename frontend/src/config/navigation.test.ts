import { describe, expect, it } from "vitest";
import { allPages, navigation } from "./navigation";

describe("融合版导航基线", () => {
  it("包含新平台全部 78 个页面", () => {
    expect(allPages).toHaveLength(78);
  });

  it("页面编号和路由均唯一", () => {
    expect(new Set(allPages.map((page) => page.code)).size).toBe(78);
    expect(new Set(allPages.map((page) => page.path)).size).toBe(78);
  });

  it("十个业务分组数量与基线一致", () => {
    expect(navigation.map((group) => group.pages.length)).toEqual([7, 7, 7, 8, 8, 7, 7, 8, 7, 11]);
  });

  it("所有页面都有中文标题、说明和 /app 路由", () => {
    for (const page of allPages) {
      expect(page.title).toMatch(/[\u4e00-\u9fff]/);
      expect(page.description.length).toBeGreaterThan(10);
      expect(page.path.startsWith("/app/")).toBe(true);
    }
  });
});
