/* Obsidian Sentinel / application shell: dark by default so the control room reads as a live operations surface. */

import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import NotFound from "@/pages/NotFound";
import { Route, Switch } from "wouter";
import ErrorBoundary from "./components/ErrorBoundary";
import { ThemeProvider } from "./contexts/ThemeContext";
import Overview from "./pages/Overview";
import { AuditReceipts, SystemArchitecture, SystemDocs } from "./pages/SystemViews";
import ControlRoom from "./pages/ControlRoom";

function Router() {
  return (
    <Switch>
      <Route path="/" component={Overview} />
      <Route path="/architecture" component={SystemArchitecture} />
      <Route path="/control-room" component={ControlRoom} />
      <Route path="/audit" component={AuditReceipts} />
      <Route path="/docs" component={SystemDocs} />
      <Route path="/404" component={NotFound} />
      <Route component={NotFound} />
    </Switch>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider defaultTheme="dark">
        <TooltipProvider>
          <Toaster />
          <Router />
        </TooltipProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}
