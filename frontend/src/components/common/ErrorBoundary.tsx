import { Component, type ErrorInfo, type ReactNode } from "react";

/**
 * Перехватывает ошибки отрисовки: вместо пустого экрана показывает, что произошло,
 * и даёт продолжить работу без перезагрузки всего приложения.
 * resetKey (например, адрес страницы) сбрасывает ошибку при переходе на другую страницу.
 */
export class ErrorBoundary extends Component<{ children: ReactNode; resetKey?: string }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Ошибка отрисовки страницы:", error, info.componentStack);
  }

  componentDidUpdate(prev: { resetKey?: string }) {
    if (this.state.error && prev.resetKey !== this.props.resetKey) this.setState({ error: null });
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    // NotFoundError при insertBefore/removeChild — типичный след расширения браузера, меняющего страницу
    const domConflict = /insertBefore|removeChild|NotFoundError/.test(`${error.name} ${error.message}`);
    return (
      <div role="alert" className="rounded-lg border border-destructive/40 bg-card p-6 max-w-2xl">
        <h2 className="text-lg font-semibold text-foreground">Страница не смогла отобразиться</h2>
        <p className="text-sm text-muted-foreground mt-2">
          {domConflict
            ? "Похоже, страницу изменяет расширение браузера (переводчик, проверка орфографии, тёмная тема). Отключите его для этого сайта или откройте сайт в режиме инкогнито."
            : "Данные сохранены. Попробуйте продолжить — если ошибка повторится, сообщите текст ниже."}
        </p>
        <pre className="mt-3 text-xs text-muted-foreground whitespace-pre-wrap break-words bg-surface rounded-md p-3 max-h-40 overflow-auto">
          {error.name}: {error.message}
        </pre>
        <div className="mt-4 flex gap-2">
          <button className="h-9 px-4 rounded-md bg-primary text-primary-foreground text-sm"
            onClick={() => this.setState({ error: null })}>Продолжить</button>
          <button className="h-9 px-4 rounded-md border border-border text-sm text-foreground"
            onClick={() => window.location.reload()}>Обновить страницу</button>
        </div>
      </div>
    );
  }
}
