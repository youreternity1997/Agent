export interface ToolInfo {
  id: string;
  name: string;
  description: string;
}

export interface SkillInfo {
  id: string;
  title: string;
  description: string;
}

export async function fetchTools(): Promise<ToolInfo[]> {
  const res = await fetch("/api/tools");
  if (!res.ok) throw new Error(`載入工具清單失敗 (${res.status})`);
  return res.json();
}

export async function fetchSkills(): Promise<SkillInfo[]> {
  const res = await fetch("/api/skills");
  if (!res.ok) throw new Error(`載入 Skill 清單失敗 (${res.status})`);
  return res.json();
}
