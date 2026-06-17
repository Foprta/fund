export default function Page() {
  return (
    <div className="mx-auto flex min-h-[60vh] w-full max-w-3xl flex-col justify-center px-4 py-12">
      <p className="text-sm font-medium text-muted-foreground">Error</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight">
        Something went wrong.
      </h1>
      <p className="mt-3 text-muted-foreground">
        Try refreshing the page or returning home.
      </p>
      <a
        href="/"
        className="mt-6 text-sm font-medium underline underline-offset-4"
      >
        Return home
      </a>
    </div>
  );
}
