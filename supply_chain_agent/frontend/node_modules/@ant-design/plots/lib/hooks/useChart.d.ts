import { Chart, CommonConfig } from '../interface';
export default function useChart<T extends Chart, U extends CommonConfig>(ChartClass: T, config: U): {
    chart: import("react").MutableRefObject<T>;
    container: import("react").MutableRefObject<HTMLDivElement>;
};
