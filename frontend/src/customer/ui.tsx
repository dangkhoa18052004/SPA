// Locally owned shadcn/ui primitives, adapted for Bin Spa's customer theme.
// https://ui.shadcn.com/docs/components/radix/button (MIT)
import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs));
const buttonVariants = cva('inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-primary disabled:pointer-events-none disabled:opacity-50', {
  variants: { variant: { default: 'bg-primary text-primary-foreground hover:bg-primary/90', outline: 'border border-border bg-card hover:bg-secondary text-foreground', ghost: 'hover:bg-secondary text-foreground' } },
  defaultVariants: { variant: 'default' }
});
export const Button = React.forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof buttonVariants> & { asChild?: boolean }>(
  ({ className, variant, asChild, type = 'button', ...props }, ref) => {
    const Component = asChild ? Slot : 'button';
    return <Component ref={ref} {...(!asChild ? { type } : {})} className={cn(buttonVariants({ variant }), className)} {...props} />;
  });
Button.displayName = 'Button';
export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('rounded-2xl border border-border bg-card p-5 text-card-foreground shadow-sm sm:p-7', className)} {...props} />;
}
export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(({ className, ...props }, ref) =>
  <input ref={ref} className={cn('min-h-11 w-full min-w-0 rounded-xl border border-border bg-card px-3 py-2 text-base outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50', className)} {...props} />);
Input.displayName = 'Input';
export const selectClass = 'min-h-11 w-full min-w-0 rounded-xl border border-border bg-card px-3 py-2 text-base focus-visible:outline-primary';

export function LoadingState({ children = 'Đang tải…' }: { children?: React.ReactNode }) {
  return <Card aria-busy="true"><p role="status" className="text-muted-foreground">{children}</p></Card>;
}
