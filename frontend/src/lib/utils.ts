import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import type { User } from '@/types/user'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function isAdmin(user: User | null | undefined): boolean {
  return user?.role === 'admin' || user?.role === 'org_admin'
}
