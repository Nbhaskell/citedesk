import { Route, Routes } from "react-router-dom";
import { LiveRegionProvider } from "./components/LiveRegion";
import { Shell } from "./components/Shell";
import { DetailScreen } from "./screens/detail/DetailScreen";
import { QueueScreen } from "./screens/queue/QueueScreen";
import { InsightsScreen, NotFoundScreen, SettingsScreen } from "./screens/Placeholder";

/** The routes. The router and the API client are provided by the caller (main.tsx, or a test). */
export function App() {
  return (
    <LiveRegionProvider>
      <Routes>
        <Route element={<Shell />}>
          <Route index element={<QueueScreen />} />
          <Route path="inquiries/:id" element={<DetailScreen />} />
          <Route path="insights" element={<InsightsScreen />} />
          <Route path="settings" element={<SettingsScreen />} />
          <Route path="*" element={<NotFoundScreen />} />
        </Route>
      </Routes>
    </LiveRegionProvider>
  );
}
