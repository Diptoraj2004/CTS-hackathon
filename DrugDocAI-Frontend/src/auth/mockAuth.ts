export interface User {
  id: string;
  email: string;
  name: string;
  role: "patient" | "admin" | "user";
}

export interface AuthResponse {
  success: boolean;
  user?: User;
  error?: string;
}

const STORAGE_KEY = "drugdoc_mock_user";

export const mockAuth = {
  login: async (
    identifier: string,
    password?: string,
    role: "user" | "admin" = "user"
  ): Promise<AuthResponse> => {
    // Simulated async delay
    await new Promise((resolve) => setTimeout(resolve, 300));

    if (!identifier || identifier.trim().length === 0) {
      return {
        success: false,
        error: role === "admin" ? "Please enter your admin ID or email." : "Please enter your email or phone number.",
      };
    }

    if (!password || password.trim().length === 0) {
      return { success: false, error: "Please enter your password." };
    }

    const user: User = {
      id: role === "admin" ? "adm_" + Math.random().toString(36).substring(2, 9) : "usr_" + Math.random().toString(36).substring(2, 9),
      email: identifier.includes("@") ? identifier : `${identifier}@drugdoc.ai`,
      name: identifier.split("@")[0],
      role: role === "admin" ? "admin" : "user",
    };

    localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
    return { success: true, user };
  },

  register: async (
    name: string,
    email: string,
    password?: string
  ): Promise<AuthResponse> => {
    // Simulated async delay
    await new Promise((resolve) => setTimeout(resolve, 300));

    if (!name || name.trim().length === 0) {
      return { success: false, error: "Please enter your full name." };
    }

    if (!email || email.trim().length === 0) {
      return { success: false, error: "Please enter your email address." };
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email.trim())) {
      return { success: false, error: "Please enter a valid email address." };
    }

    if (!password || password.length < 8) {
      return { success: false, error: "Password must be at least 8 characters long." };
    }

    const user: User = {
      id: "usr_" + Math.random().toString(36).substring(2, 9),
      email: email.trim(),
      name: name.trim(),
      role: "user",
    };

    localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
    return { success: true, user };
  },

  logout: (): void => {
    localStorage.removeItem(STORAGE_KEY);
  },

  getCurrentUser: (): User | null => {
    const data = localStorage.getItem(STORAGE_KEY);
    if (!data) return null;
    try {
      return JSON.parse(data) as User;
    } catch {
      return null;
    }
  },

  isAuthenticated: (): boolean => {
    return !!localStorage.getItem(STORAGE_KEY);
  },
};
