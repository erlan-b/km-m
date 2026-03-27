import { BrowserRouter } from "react-router-dom";

import { AuthProvider } from "./app/auth/AuthContext";
import { I18nProvider } from "./app/i18n/I18nContext";
import { AppRouter } from "./app/router/AppRouter";

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <I18nProvider>
          <AppRouter />
        </I18nProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
