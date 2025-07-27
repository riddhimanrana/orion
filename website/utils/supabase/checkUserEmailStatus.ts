import { createClient } from "@/utils/supabase/client";

export async function checkUserEmailStatus(email: string): Promise<{ user_exists: boolean; email_confirmed: boolean }> {
  const supabase = createClient();
  const { data, error } = await supabase.rpc("check_user_email_status", { input_email: email });
  if (error) {
    throw new Error(error.message);
  }
  // The function returns an array of rows, but we only care about the first one
  if (Array.isArray(data) && data.length > 0) {
    return data[0];
  }
  // If no data, treat as not found
  return { user_exists: false, email_confirmed: false };
}
