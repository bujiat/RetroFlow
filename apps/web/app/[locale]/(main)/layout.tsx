import { AuthGate } from "@/components/auth-gate";
import { AppShell } from "@/components/app-shell";

export default function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGate>
      <AppShell>
        <div className="mx-auto max-w-[960px] px-6 py-8 lg:px-10 lg:py-10">{children}</div>
      </AppShell>
    </AuthGate>
  );
}
