export interface ArrayRescaleOptions<T extends ArrayLike<number>> {
    /**
     * @default 0
     */
    min?: number;
    /**
     * @default 1
     */
    max?: number;
    /**
     * If `true` and min or max is undefined take the min or max from input array.
     * @default false
     */
    autoMinMax?: boolean;
    /**
     * Specify the output array. Can be the input array for in place modification.
     */
    output?: T;
}
/**
 * Rescale an array into a range.
 */
export default function rescale<T extends ArrayLike<number>>(input: T, options?: ArrayRescaleOptions<T>): T | number[];
//# sourceMappingURL=index.d.ts.map