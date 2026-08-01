import Link from "next/link";
import type {
  ComponentPropsWithRef,
  ComponentPropsWithoutRef,
  ReactNode,
} from "react";

import styles from "./Button.module.css";

export type ButtonVariant =
  | "primary"
  | "secondary"
  | "quiet"
  | "outline"
  | "ghost"
  | "destructive";

export type ButtonSize =
  | "sm"
  | "md"
  | "nav"
  | "navLg"
  | "lg"
  | "hero"
  | "cta"
  | "block";

type BaseProps = {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  children: ReactNode;
  className?: string;
};

function classes({ variant = "primary", size = "md", className }: BaseProps) {
  return [styles.btn, styles[variant], styles[size], className]
    .filter(Boolean)
    .join(" ");
}

export function Button({
  variant,
  size,
  loading,
  children,
  className,
  ...rest
}: BaseProps & ComponentPropsWithRef<"button">) {
  return (
    <button
      className={classes({ variant, size, className, children })}
      {...rest}
    >
      {loading ? <span className={styles.spinner} aria-hidden="true" /> : null}
      {children}
    </button>
  );
}

export function ButtonLink({
  variant,
  size,
  children,
  className,
  href,
  ...rest
}: BaseProps & { href: string } & Omit<
    ComponentPropsWithoutRef<typeof Link>,
    "href" | "className" | "children"
  >) {
  return (
    <Link
      href={href}
      className={classes({ variant, size, className, children })}
      {...rest}
    >
      {children}
    </Link>
  );
}
