import { AppFooter } from "@/components/layout/AppFooter";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { OptimizationSweepProvider } from "@/contexts/OptimizationSweepContext";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <OptimizationSweepProvider>
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <TopBar />
          <main className="flex-1 p-6 lg:p-8">{children}</main>
          <AppFooter />
        </div>
      </div>
    </OptimizationSweepProvider>
  );
}
