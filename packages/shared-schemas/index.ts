export const projectStatuses = [
  "draft",
  "requirements_uploaded",
  "requirements_structured",
  "requirements_confirmed",
  "code_generated",
  "tests_generated",
  "deployed",
  "failed",
] as const;

export type ProjectStatus = (typeof projectStatuses)[number];

