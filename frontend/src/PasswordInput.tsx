import { useId, useState, type InputHTMLAttributes } from 'react';
import './auth.css';

export const passwordInputType = (visible: boolean) => visible ? 'text' : 'password';

export function PasswordInput({ label = 'Password', ...props }: Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> & { label?: string }) {
  const id = useId();
  const [visible, setVisible] = useState(false);
  return <div className="password-field">
    <label className="label-text" htmlFor={props.id || id}>{label}</label>
    <div className="password-control">
      <input {...props} id={props.id || id} type={passwordInputType(visible)} />
      <button type="button" className="secondary" aria-label={`${visible ? 'Hide' : 'Show'} ${label.toLowerCase()}`} aria-pressed={visible} aria-controls={props.id || id} onClick={() => setVisible(value => !value)}>{visible ? 'Hide' : 'Show'}</button>
    </div>
  </div>;
}
