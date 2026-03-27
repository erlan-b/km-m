import { BrowserRouter } from "react-router-dom";

import { AuthProvider } from "./app/auth/AuthContext";
import { AppRouter } from "./app/router/AppRouter";

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRouter />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
