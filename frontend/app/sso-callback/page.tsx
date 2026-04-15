import { AuthenticateWithRedirectCallback } from '@clerk/nextjs'
import LoadingWordmark from '@/components/LoadingWordmark'

export default function SSOCallbackPage() {
  return (
    <>
      <LoadingWordmark />
      <AuthenticateWithRedirectCallback afterSignInUrl="/create" afterSignUpUrl="/create" />
    </>
  )
}
