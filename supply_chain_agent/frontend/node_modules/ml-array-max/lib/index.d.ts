export interface ArrayMaxOptions {
    /**
     * Start index (inclusive) for the slice within which we look for the maximum.
     * @default 0
     */
    fromIndex?: number;
    /**
     * End index (exclusive) for the slice within which we look for the maximum.
     * @default input.length
     */
    toIndex?: number;
}
/**
 * Computes the maximum of the given values.
 *
 * @param input
 * @param options
 */
export default function max(input: ArrayLike<number>, options?: ArrayMaxOptions): number;
//# sourceMappingURL=index.d.ts.map