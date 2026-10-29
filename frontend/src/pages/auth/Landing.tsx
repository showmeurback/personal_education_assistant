import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/layout/Logo";
import { PipelineHero } from "@/components/landing/PipelineHero";
import { ThemeToggle } from "@/components/layout/ThemeToggle";

const features = [
  {
    title: "Проверка отчётов с объяснением",
    text: "Точные правила отсеивают явные проблемы и списывание, искусственный интеллект проверяет отчёт по смыслу, а спорные случаи решает преподаватель. Каждый шаг виден в протоколе.",
  },
  {
    title: "Ассистент по материалам курса",
    text: "Отвечает на вопросы, опираясь на загруженные преподавателем лекции, и показывает, из каких файлов взят ответ.",
  },
  {
    title: "Тесты и пробный экзамен",
    text: "Вопросы генерируются по материалам курса, а оценка выставляется по фиксированной шкале — одинаково для всех.",
  },
  {
    title: "Подбор курсов",
    text: "Рекомендации учитывают ваши интересы, оценки других студентов и смысловую близость описания курса к вашим целям.",
  },
];

export default function Landing() {
  return (
    <div className="min-h-screen bg-background">
      <header className="flex items-center justify-between px-5 sm:px-10 h-16 border-b border-border">
        <Logo />
        <div className="flex items-center gap-2">
          <ThemeToggle />
          {/* на узком экране вход — кнопкой «У меня есть аккаунт» под заголовком */}
          <Link to="/login" className="hidden sm:block"><Button variant="ghost">Войти</Button></Link>
          <Link to="/register"><Button>Создать аккаунт</Button></Link>
        </div>
      </header>

      <section className="px-5 sm:px-10 pt-14 pb-16 max-w-6xl mx-auto grid lg:grid-cols-[1fr_1.1fr] gap-12 items-center">
        <div>
          <h1 className="text-3xl sm:text-[44px] leading-[1.1] text-foreground">
            Персональный ассистент по обучению
          </h1>
          <p className="mt-5 text-lg text-muted-foreground max-w-xl leading-relaxed">
            Помогает студентам учиться, а преподавателям любых дисциплин — проверять отчёты:
            точные правила там, где ответ должен быть проверяемым, и искусственный интеллект там,
            где нужно понимать смысл текста.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/register"><Button size="lg">Начать обучение</Button></Link>
            <Link to="/login"><Button size="lg" variant="outline">У меня есть аккаунт</Button></Link>
          </div>
        </div>
        <figure className="rounded-lg border border-border bg-card p-5 sm:p-7">
          <PipelineHero />
          <figcaption className="mt-3 text-sm text-muted-foreground">
            Как проверяется отчёт: квадраты — проверка по точным правилам, круги — искусственный интеллект.
            До ИИ доходят только отчёты, которые прошли формальную проверку.
          </figcaption>
        </figure>
      </section>

      <section className="px-5 sm:px-10 pb-20 max-w-6xl mx-auto">
        <div className="grid sm:grid-cols-2 gap-x-10 gap-y-8 border-t border-border pt-10">
          {features.map((f) => (
            <div key={f.title}>
              <h2 className="font-body text-base font-semibold text-foreground">{f.title}</h2>
              <p className="mt-1.5 text-sm text-muted-foreground leading-relaxed max-w-md">{f.text}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
