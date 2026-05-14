import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { endpoints } from "../lib/api";
import { Badge, Button, Card, Page, SecondaryButton, TextArea, TextField } from "../components/ui";

const createProjectSchema = z.object({
  name: z.string().min(3),
  description: z.string().optional().default(""),
});

type CreateProjectSchema = z.infer<typeof createProjectSchema>;

export function DashboardPage() {
  const queryClient = useQueryClient();
  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: async () => (await endpoints.projects()).data,
  });
  const createProject = useMutation({
    mutationFn: async (payload: CreateProjectSchema) => (await endpoints.createProject(payload)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      reset();
    },
  });
  const { register, handleSubmit, formState: { errors }, reset } = useForm<CreateProjectSchema>({
    resolver: zodResolver(createProjectSchema),
    defaultValues: { name: "", description: "" },
  });

  return (
    <Page
      title="Проектный дашборд"
      subtitle="Создавайте проекты, запускайте CASE pipeline и переходите к структуре требований, генерации, тестам и деплою."
      actions={<SecondaryButton onClick={() => queryClient.invalidateQueries({ queryKey: ["projects"] })}>Обновить</SecondaryButton>}
    >
      <div className="grid gap-6 lg:grid-cols-[420px,1fr]">
        <Card title="Создать проект">
          <form className="space-y-4" onSubmit={handleSubmit((values) => createProject.mutate(values))}>
            <div>
              <label className="mb-2 block text-sm text-slate-300">Название</label>
              <TextField {...register("name")} placeholder="CASE Demo Project" />
              {errors.name ? <div className="mt-2 text-xs text-rose-300">{errors.name.message}</div> : null}
            </div>
            <div>
              <label className="mb-2 block text-sm text-slate-300">Описание</label>
              <TextArea {...register("description")} placeholder="Краткое описание проекта" />
            </div>
            <Button type="submit" disabled={createProject.isPending}>
              {createProject.isPending ? "Создание..." : "Создать проект"}
            </Button>
          </form>
        </Card>
        <Card title="Проекты">
          <div className="grid gap-4">
            {projectsQuery.data?.map((project) => (
              <Link
                key={project.id}
                to={`/projects/${project.id}`}
                className="rounded-2xl border border-white/10 bg-white/5 p-4 transition hover:border-orange-400/50 hover:bg-white/10"
              >
                <div className="mb-2 flex items-center justify-between gap-3">
                  <div className="text-lg font-medium">{project.name}</div>
                  <Badge tone={project.status === "deployed" ? "success" : "default"}>{project.status}</Badge>
                </div>
                <div className="text-sm text-slate-300">{project.description || "Без описания"}</div>
              </Link>
            ))}
            {!projectsQuery.data?.length ? <div className="text-sm text-slate-400">Проекты ещё не созданы.</div> : null}
          </div>
        </Card>
      </div>
    </Page>
  );
}

